import asyncio
import json
import re
from uuid import UUID, uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import SESSION_COOKIE
from app.auth.sessions import resolve_session
from app.core.config import get_settings
from app.db.session import get_engine
from app.services.realtime import HEARTBEAT_SECONDS, MAX_SUBSCRIPTIONS, VIN_PATTERN, Peer, RealtimeHub, frame

router = APIRouter()
MAX_MESSAGE_BYTES = 4096
MAX_COMMANDS_PER_MINUTE = 60


def session_identity(token: str) -> tuple[UUID, bool] | None:
    # Close the DB session before waiting on any socket I/O.
    with Session(get_engine()) as db:
        resolved = resolve_session(db, token)
        if resolved:
            _, user = resolved
            return user.id, user.must_change_password
    return None


def same_origin(ws: WebSocket) -> bool:
    scheme = "https" if ws.url.scheme == "wss" else "http"
    if scheme != "https" and get_settings().cookie_secure:
        return False
    host = ws.headers.get("host")
    return bool(host) and ws.headers.getlist("origin") == [f"{scheme}://{host}"]


async def send(ws: WebSocket, message: dict) -> None:
    await asyncio.wait_for(ws.send_json(message), 5)


async def protocol_error(ws: WebSocket, code: str, detail: str, close_code: int = 4400) -> None:
    await send(ws, frame("error", {"code": code, "message": detail}))
    await ws.close(close_code)


async def command(ws: WebSocket, hub: RealtimeHub, peer: Peer, raw: str | None) -> bool:
    try:
        if raw is None or len(raw.encode()) > MAX_MESSAGE_BYTES:
            raise ValueError
        message = json.loads(raw)
        if not isinstance(message, dict) or set(message) != {"v", "type", "request_id", "data"}:
            raise ValueError
        request_id = message["request_id"]
        if not isinstance(request_id, str) or len(request_id) != 36 or str(UUID(request_id)) != request_id.lower():
            raise ValueError
        if not isinstance(message["data"], dict):
            raise ValueError
    except (ValueError, RecursionError):
        await protocol_error(ws, "invalid_message", "Send a JSON v1 command with a UUID request_id.")
        return False

    if type(message["v"]) is not int or message["v"] != 1:
        await protocol_error(ws, "unsupported_version", "Only protocol version 1 is supported.")
        return False
    kind, data = message["type"], message["data"]
    if kind == "ping" and not data:
        await send(ws, frame("pong", {}, request_id))
        return True
    if kind == "ping":
        await protocol_error(ws, "invalid_message", "A ping must have an empty data object.")
        return False
    if kind not in ("timeline.subscribe", "timeline.unsubscribe"):
        await protocol_error(ws, "unknown_type", "This command is not supported.")
        return False
    vin = data.get("vin")
    if set(data) != {"vin"} or not isinstance(vin, str) or not re.fullmatch(VIN_PATTERN, vin):
        await protocol_error(ws, "invalid_vin", "Use a canonical VIN with 17 characters.")
        return False
    if kind == "timeline.subscribe":
        if vin not in peer.vins and len(peer.vins) >= MAX_SUBSCRIPTIONS:
            await protocol_error(ws, "subscription_limit", "Too many timeline subscriptions.", 4429)
            return False
        # The timeline itself is public. The socket requires a signed-in user for private invalidations.
        hub.watch(peer, vin)
        await send(ws, frame("timeline.subscribed", {"vin": vin}, request_id))
    else:
        hub.unwatch(peer, vin)
        await send(ws, frame("timeline.unsubscribed", {"vin": vin}, request_id))
    return True


async def connected(ws: WebSocket, hub: RealtimeHub, peer: Peer, token: str) -> None:
    await send(ws, frame("connection.ready", {
        "connection_id": str(uuid4()), "heartbeat_seconds": HEARTBEAT_SECONDS,
        "max_timeline_subscriptions": MAX_SUBSCRIPTIONS,
    }))
    clock = asyncio.get_running_loop().time
    last_command = window = clock()
    recheck = last_command + HEARTBEAT_SECONDS
    count = 0
    incoming = asyncio.create_task(ws.receive())
    outgoing = asyncio.create_task(peer.outbound.get())
    try:
        while True:
            deadline = min(recheck, last_command + 2 * HEARTBEAT_SECONDS)
            done, _ = await asyncio.wait((incoming, outgoing), timeout=max(0, deadline - clock()),
                                         return_when=asyncio.FIRST_COMPLETED)
            now = clock()
            if now >= recheck:
                if await run_in_threadpool(session_identity, token) != (peer.user_id, False):
                    await ws.close(4401)
                    return
                recheck = now + HEARTBEAT_SECONDS
            if incoming in done:
                message = incoming.result()
                if message["type"] == "websocket.disconnect":
                    return
                if now - window >= 60:
                    window, count = now, 0
                count += 1
                if count > MAX_COMMANDS_PER_MINUTE:
                    await ws.close(4429)
                    return
                if not await command(ws, hub, peer, message.get("text")):
                    return
                last_command = now
                incoming = asyncio.create_task(ws.receive())
            elif now - last_command >= 2 * HEARTBEAT_SECONDS:
                await ws.close(4408)
                return
            if outgoing in done:
                message = outgoing.result()
                if isinstance(message, int):
                    await ws.close(message)
                    return
                if not peer.closed:
                    # Discard any record queued just before the client unsubscribed.
                    if message["type"] != "record.added" or message["data"]["vin"] in peer.vins:
                        await send(ws, message)
                outgoing = asyncio.create_task(peer.outbound.get())
    finally:
        for task in (incoming, outgoing):
            task.cancel()
        await asyncio.gather(incoming, outgoing, return_exceptions=True)


@router.websocket("/api/v1/ws")
async def websocket_events(ws: WebSocket) -> None:
    if not same_origin(ws):
        await ws.close(4403)  # pre-upgrade: reject with HTTP 403
        return
    token = ws.cookies.get(SESSION_COOKIE, "")
    identity = await run_in_threadpool(session_identity, token) if token else None
    await ws.accept()
    if identity is None or identity[1]:
        await ws.close(4401 if identity is None else 4403)
        return
    hub: RealtimeHub = ws.app.state.realtime
    if not hub.available:
        await ws.close(1013)
        return
    peer = hub.attach(identity[0])
    try:
        await connected(ws, hub, peer, token)
    except (WebSocketDisconnect, TimeoutError):
        pass
    finally:
        hub.detach(peer)
