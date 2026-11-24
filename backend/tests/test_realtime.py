import asyncio
import os
from contextlib import ExitStack
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.api.v1 import websocket
from app.auth.dependencies import SESSION_COOKIE
from app.models import MemberRole, Notification, Watchlist
from app.services import events
from app.services.realtime import CHANNEL, Publication, realtime
from tests.auth_helpers import add_member, add_user, csrf, login
from tests.factories import make_org, make_vehicle

URL = "wss://testserver/api/v1/ws"
ORIGIN = "https://testserver"
VIN = "JTMHX01J5M4012345"
OTHER_VIN = "JN8AY2NY4K9012345"


def headers(token: str, origin: str = ORIGIN) -> dict[str, str]:
    return {"Origin": origin, "Cookie": f"{SESSION_COOKIE}={token}"}


def send(ws, kind: str, data: dict, version: int = 1) -> str:
    request_id = str(uuid4())
    ws.send_json({"v": version, "type": kind, "request_id": request_id, "data": data})
    return request_id


def record_payload(vin: str) -> dict:
    return {"vin": vin, "record_id": str(uuid4()), "service_date": "2026-11-20",
            "is_mileage_flagged": False, "corrects_record_id": None, "notes": "private"}


def notice_payload(recipient: UUID) -> dict:
    return {"user_id": str(recipient), "notification_id": str(uuid4()), "event_type": "record.added",
            "created_at": datetime.now(UTC).isoformat()}


def test_websocket_subscriptions_and_private_notifications(app: FastAPI, monkeypatch) -> None:
    owner, other = uuid4(), uuid4()
    identities = {"owner": (owner, False), "other": (other, False)}
    monkeypatch.setattr(websocket, "session_identity", identities.get)
    with TestClient(app) as client, ExitStack() as sockets:
        a = sockets.enter_context(client.websocket_connect(URL, headers=headers("owner")))
        b = sockets.enter_context(client.websocket_connect(URL, headers=headers("other")))
        for ws, vin in ((a, VIN), (b, OTHER_VIN)):
            assert ws.receive_json()["type"] == "connection.ready"
            request_id = send(ws, "timeline.subscribe", {"vin": vin})
            assert ws.receive_json()["request_id"] == request_id
            request_id = send(ws, "ping", {})
            pong = ws.receive_json()
            assert (pong["type"], pong["request_id"]) == ("pong", request_id)
        first, second = record_payload(VIN), record_payload(OTHER_VIN)
        events.publish("record.added", first)
        events.publish("record.added", second)
        for ws, payload in ((a, first), (b, second)):
            message = ws.receive_json()
            assert message["type"] == "record.added"
            assert message["data"] == {key: value for key, value in payload.items() if key != "notes"}
        private_a, private_b = notice_payload(owner), notice_payload(other)
        events.publish("notification.created", private_a)
        events.publish("notification.created", private_b)
        for ws, payload in ((a, private_a), (b, private_b)):
            message = ws.receive_json()
            assert message["type"] == "notification.created"
            assert message["data"]["notification_id"] == payload["notification_id"]
            assert "user_id" not in message["data"]
        send(a, "timeline.unsubscribe", {"vin": VIN})
        assert a.receive_json()["type"] == "timeline.unsubscribed"
        events.publish("record.added", record_payload(VIN))
        events.publish("notification.created", private_a)
        assert a.receive_json()["type"] == "notification.created"
    assert not app.state.realtime.by_user and not app.state.realtime.by_vin


def test_websocket_checks_origin_session_and_protocol(app: FastAPI, monkeypatch) -> None:
    owner = uuid4()
    monkeypatch.setattr(websocket, "session_identity", {"owner": (owner, False), "temp": (owner, True)}.get)
    with TestClient(app) as client:
        for token, origin, code in (("owner", "https://other.test", 4403), ("unknown", ORIGIN, 4401), ("temp", ORIGIN, 4403)):
            with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect(URL, headers=headers(token, origin)) as ws:
                ws.receive_json()
            assert exc.value.code == code
        with client.websocket_connect(URL, headers=headers("owner")) as ws:
            ws.receive_json()
            send(ws, "timeline.subscribe", {"vin": "INVALID"})
            assert ws.receive_json()["data"]["code"] == "invalid_vin"
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
            assert exc.value.code == 4400


@pytest.mark.parametrize("revoked, code", [(True, 4401), (False, 4408)])
def test_existing_socket_rechecks_session_and_expires_idle_peers(app: FastAPI, monkeypatch, revoked, code) -> None:
    identities = {"owner": (uuid4(), False)}
    monkeypatch.setattr(websocket, "session_identity", identities.get)
    monkeypatch.setattr(websocket, "HEARTBEAT_SECONDS", 0.05)
    with TestClient(app) as client, client.websocket_connect(URL, headers=headers("owner")) as ws:
        assert ws.receive_json()["type"] == "connection.ready"
        if revoked:
            identities.clear()
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == code


def test_redis_fans_out_to_independent_connections() -> None:
    url = os.environ.get("TEST_REDIS_URL")
    if not url:
        pytest.skip("Set TEST_REDIS_URL to run against an isolated Redis instance")

    async def exercise() -> None:
        payload = record_payload(VIN)
        async with realtime(url) as left, realtime(url) as right, Redis.from_url(url) as producer:
            a, b = left.attach(uuid4()), right.attach(uuid4())
            left.watch(a, VIN)
            right.watch(b, VIN)
            async with asyncio.timeout(5):
                while not (left.available and right.available):
                    await asyncio.sleep(0.01)
                event = Publication(type="record.added", data=payload)
                assert await producer.publish(CHANNEL, event.model_dump_json()) >= 2
                for peer in (a, b):
                    message = await peer.outbound.get()
                    assert message["data"]["record_id"] == payload["record_id"]

    asyncio.run(exercise())


def test_committed_record_creates_only_enabled_watch_alerts(client: TestClient, db: Session) -> None:
    org, vehicle = make_org(db), make_vehicle(db, VIN)
    writer = add_user(db, "realtime.writer@example.ae")
    watcher = add_user(db, "realtime.watcher@example.ae")
    muted = add_user(db, "realtime.muted@example.ae")
    add_member(db, org, writer, MemberRole.ENTITY_STAFF)
    db.add_all([
        Watchlist(user_id=watcher.id, vehicle_id=vehicle.id),
        Watchlist(user_id=muted.id, vehicle_id=vehicle.id, notifications_enabled=False),
    ])
    assert login(client, writer.email).status_code == 200
    response = client.post(f"/api/v1/organizations/{org.id}/records", headers=csrf(client), json={
        "vin": VIN, "category": "maintenance", "service_date": "2025-01-01", "odometer_km": 10000,
        "work_codes": ["OIL_CHANGE"], "notes": "private note",
    })
    assert response.status_code == 201, response.text
    assert client.get("/api/v1/notifications").json() == []
    client.cookies.clear()
    assert login(client, watcher.email).status_code == 200
    [notice] = client.get("/api/v1/notifications").json()
    assert notice["vin"] == VIN and notice["record_id"] == response.json()["id"]
    assert db.get(Notification, UUID(notice["id"])).user_id == watcher.id
    assert "notes" not in notice and "user_id" not in notice
    client.cookies.clear()
    assert login(client, muted.email).status_code == 200
    assert client.get("/api/v1/notifications").json() == []
