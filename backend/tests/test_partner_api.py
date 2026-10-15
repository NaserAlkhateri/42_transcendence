from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ApiKey, AuditEvent, MemberRole, PartnerWatchlist, ServiceRecord, UserRole
from app.services.rate_limit import RateLimiter, partner_limiter
from tests.auth_helpers import add_member, add_user, csrf, login
from tests.factories import make_org, make_record, make_vehicle

P = "/api/partner/v1"
KEYS = "/api/v1/admin/api-keys"
VIN = "JTMHX01J5M4012345"


@pytest.fixture(autouse=True)
def fresh_limits():
    partner_limiter.reset()
    yield
    partner_limiter.reset()


@pytest.fixture
def admin_client(app: FastAPI, db: Session):
    add_user(db, "root@example.ae", role=UserRole.PLATFORM_ADMIN)
    with TestClient(app, base_url="https://testserver") as admin:
        login(admin, "root@example.ae")
        yield admin


def issue(admin: TestClient, partner_name: str = "Gulf Shield Insurance") -> dict:
    response = admin.post(KEYS, json={"partner_name": partner_name}, headers=csrf(admin))
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def partner(app: FastAPI, admin_client: TestClient):
    """A cookie-less client that sends a freshly issued key, as an insurer's server would."""
    issued = issue(admin_client)
    with TestClient(app, base_url="https://testserver", headers={"X-API-Key": issued["api_key"]}) as client:
        client.issued = issued  # type: ignore[attr-defined]
        yield client


@pytest.fixture
def history(db: Session):
    """A Land Cruiser with a normal record, a flagged lower reading and a correction of a mistyped one."""
    org = make_org(db, name="Falcon Bay Auto Care")
    staff = add_user(db, "staff@example.ae", full_name="Arjun Nair")
    add_member(db, org, staff, MemberRole.ENTITY_STAFF)
    vehicle = make_vehicle(db, VIN)
    make_record(db, vehicle, org, staff, odometer_km=40_000, service_date=date(2025, 6, 1), notes="private note")
    make_record(db, vehicle, org, staff, odometer_km=30_000, service_date=date(2025, 9, 1), flagged=True)
    typo = make_record(db, vehicle, org, staff, odometer_km=900_000, service_date=date(2026, 1, 10))
    make_record(db, vehicle, org, staff, odometer_km=52_000, service_date=date(2026, 1, 10), corrects=typo)
    return vehicle


# --- issuing and revoking keys (admin) -------------------------------------------------------------


def test_admin_issues_a_key_shown_once_and_stored_hashed(db: Session, admin_client: TestClient) -> None:
    issued = issue(admin_client)

    raw = issued["api_key"]
    assert raw.startswith("sjl_") and len(raw) > 40
    key = issued["key"]
    assert raw.split("_")[1] == key["key_prefix"]
    assert (key["partner_name"], key["issued_by"], key["revoked_at"], key["watch_count"]) == (
        "Gulf Shield Insurance", "root@example.ae", None, 0,
    )
    stored = db.scalar(select(ApiKey).where(ApiKey.key_prefix == key["key_prefix"]))
    secret = raw.split("_", 2)[2]
    assert secret not in stored.key_hash and len(stored.key_hash) == 64
    assert set(stored.scopes) == {"vehicles:read", "watches:manage"}
    assert "api_key" not in str(admin_client.get(KEYS).json())  # never listed again
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "api_key.issued"))
    assert raw not in str(event.details)


def test_only_platform_admins_manage_keys(client: TestClient, db: Session, admin_client: TestClient) -> None:
    key_id = issue(admin_client)["key"]["id"]
    boss = add_user(db, "boss@example.ae")
    add_member(db, make_org(db), boss, MemberRole.ENTITY_ADMIN)
    login(client, boss.email)
    assert client.get(KEYS).status_code == 403
    assert client.post(KEYS, json={"partner_name": "Sneaky"}, headers=csrf(client)).status_code == 403
    assert client.post(f"{KEYS}/{key_id}/revoke", headers=csrf(client)).status_code == 403
    assert admin_client.post(KEYS, json={"partner_name": "No CSRF"}).status_code == 403
    assert admin_client.post(KEYS, json={"partner_name": " "}, headers=csrf(admin_client)).status_code == 422


def test_revoked_key_is_refused_at_once(partner: TestClient, admin_client: TestClient, db: Session) -> None:
    assert partner.get(f"{P}/watches").status_code == 200
    key_id = partner.issued["key"]["id"]  # type: ignore[attr-defined]

    revoked = admin_client.post(f"{KEYS}/{key_id}/revoke", headers=csrf(admin_client))

    assert revoked.status_code == 200 and revoked.json()["revoked_at"] is not None
    response = partner.get(f"{P}/watches")
    assert response.status_code == 401
    assert response.json()["error"] == {"code": "invalid_api_key", "message": "This API key has been revoked."}
    assert admin_client.post(f"{KEYS}/{key_id}/revoke", headers=csrf(admin_client)).status_code == 409
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "api_key.revoked")) is not None


def test_list_shows_active_keys_first_with_usage(partner: TestClient, admin_client: TestClient) -> None:
    old = issue(admin_client, "Old Partner")["key"]["id"]
    admin_client.post(f"{KEYS}/{old}/revoke", headers=csrf(admin_client))
    partner.post(f"{P}/watches", json={"vin": VIN})

    keys = admin_client.get(KEYS).json()

    assert [k["partner_name"] for k in keys] == ["Gulf Shield Insurance", "Old Partner"]
    assert keys[0]["watch_count"] == 1 and keys[0]["last_used_at"] is not None


# --- authentication --------------------------------------------------------------------------------


@pytest.mark.parametrize("headers, code", [
    ({}, "missing_api_key"),
    ({"X-API-Key": "not-a-key"}, "invalid_api_key"),
    ({"X-API-Key": "sjl_00000000_wrongsecret"}, "invalid_api_key"),
])
def test_missing_or_unknown_keys_get_401(app: FastAPI, headers: dict, code: str) -> None:
    with TestClient(app, base_url="https://testserver") as anonymous:
        response = anonymous.get(f"{P}/vehicles/{VIN}", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == code
    assert response.headers["WWW-Authenticate"] == "ApiKey"


def test_right_prefix_wrong_secret_is_refused(app: FastAPI, partner: TestClient) -> None:
    prefix = partner.issued["key"]["key_prefix"]  # type: ignore[attr-defined]
    with TestClient(app, base_url="https://testserver") as forger:
        response = forger.get(f"{P}/watches", headers={"X-API-Key": f"sjl_{prefix}_guessed-secret"})
    assert response.status_code == 401


def test_session_cookies_do_not_open_the_partner_api(admin_client: TestClient) -> None:
    """A signed-in admin browser is not a partner: the key is the only credential here."""
    assert admin_client.get(f"{P}/watches").status_code == 401


# --- vehicle data ----------------------------------------------------------------------------------


def test_vehicle_summary_counts_history_and_uses_the_effective_reading(partner: TestClient, history) -> None:
    response = partner.get(f"{P}/vehicles/jtmhx01j5m4012345")  # VINs are normalized

    assert response.status_code == 200
    body = response.json()
    assert (body["vin"], body["make"], body["record_count"]) == (VIN, "Toyota", 4)
    assert (body["flagged_record_count"], body["correction_count"]) == (1, 1)
    # The 900,000 km typo was corrected to 52,000 km: partners see the corrected value.
    assert (body["latest_service_date"], body["latest_odometer_km"]) == ("2026-01-10", 52_000)


def test_history_is_consumer_safe(partner: TestClient, history) -> None:
    response = partner.get(f"{P}/vehicles/{VIN}/history")

    assert response.status_code == 200
    records = response.json()["records"]
    assert len(records) == 4
    assert [r["service_date"] for r in records][:2] == ["2026-01-10", "2026-01-10"]  # newest first
    text = str(response.json())
    for private in ("private note", "Arjun Nair", "notes", "staff_name", "staff_id"):
        assert private not in text
    assert any(r["is_mileage_flagged"] for r in records)
    assert any(r["corrects_record_id"] for r in records)


def test_unknown_and_invalid_vins(partner: TestClient) -> None:
    unknown = partner.get(f"{P}/vehicles/JN8AY2NY4K9012345")
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "vehicle_not_found"
    assert partner.get(f"{P}/vehicles/NOT-A-VIN/history").json()["error"]["code"] == "invalid_vin"


def test_no_partner_route_can_change_history(partner: TestClient, history, db: Session) -> None:
    before = db.scalar(select(func.count()).select_from(ServiceRecord))
    for method in ("post", "put", "patch", "delete"):
        assert getattr(partner, method)(f"{P}/vehicles/{VIN}/history").status_code == 405
        assert getattr(partner, method)(f"{P}/vehicles/{VIN}").status_code == 405
    assert partner.post("/api/v1/organizations/00000000-0000-0000-0000-000000000000/records", json={}).status_code in (401, 403)
    assert db.scalar(select(func.count()).select_from(ServiceRecord)) == before


# --- watchlist -------------------------------------------------------------------------------------


def test_watch_lifecycle_get_post_put_delete(partner: TestClient, history, db: Session) -> None:
    created = partner.post(f"{P}/watches", json={"vin": VIN, "label": "Policy 2026-00417"})
    assert created.status_code == 201
    watch = created.json()
    assert (watch["vin"], watch["label"], watch["new_record_count"]) == (VIN, "Policy 2026-00417", 0)

    # A new record arrives after the watch was set up.
    stored = db.get(PartnerWatchlist, watch["id"])
    stored.created_at = datetime.now(UTC) - timedelta(days=30)
    db.flush()
    listed = partner.get(f"{P}/watches").json()
    assert listed["total"] == 1 and listed["items"][0]["new_record_count"] == 4

    checked = partner.put(f"{P}/watches/{watch['id']}", json={"label": "Policy 2026-00418", "mark_checked": True})
    assert checked.status_code == 200
    assert (checked.json()["label"], checked.json()["new_record_count"]) == ("Policy 2026-00418", 0)
    assert partner.put(f"{P}/watches/{watch['id']}", json={}).json()["label"] is None  # PUT replaces the label

    assert partner.delete(f"{P}/watches/{watch['id']}").status_code == 204
    assert partner.get(f"{P}/watches").json() == {"items": [], "total": 0}
    assert partner.delete(f"{P}/watches/{watch['id']}").status_code == 404


def test_watch_a_vin_with_no_history_yet(partner: TestClient) -> None:
    response = partner.post(f"{P}/watches", json={"vin": "mdhbn7ad0p0-012345"})
    assert response.status_code == 201 and response.json()["vin"] == "MDHBN7AD0P0012345"
    again = partner.post(f"{P}/watches", json={"vin": "MDHBN7AD0P0012345"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_watching"
    assert partner.post(f"{P}/watches", json={"vin": "too-short"}).json()["error"]["code"] == "invalid_vin"
    assert partner.post(f"{P}/watches", json={"vin": VIN, "label": "x" * 101}).status_code == 422


def test_partners_cannot_see_or_touch_each_others_watches(app: FastAPI, partner: TestClient, admin_client: TestClient) -> None:
    mine = partner.post(f"{P}/watches", json={"vin": VIN}).json()
    other_key = issue(admin_client, "Desert Cars Marketplace")["api_key"]
    with TestClient(app, base_url="https://testserver", headers={"X-API-Key": other_key}) as other:
        assert other.get(f"{P}/watches").json()["total"] == 0
        assert other.put(f"{P}/watches/{mine['id']}", json={"label": "hijack"}).status_code == 404
        assert other.delete(f"{P}/watches/{mine['id']}").status_code == 404
    assert partner.get(f"{P}/watches").json()["items"][0]["label"] is None


def test_watch_limit_per_key(partner: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "partner_max_watches", 1)
    assert partner.post(f"{P}/watches", json={"vin": VIN}).status_code == 201
    response = partner.post(f"{P}/watches", json={"vin": "MDHBN7AD0P0012345"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "watch_limit_reached"


# --- rate limiting ---------------------------------------------------------------------------------


def test_burst_over_the_limit_gets_429_with_headers(app: FastAPI, partner: TestClient, admin_client: TestClient,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "partner_rate_limit", 3)

    first = partner.get(f"{P}/watches")
    assert (first.headers["X-RateLimit-Limit"], first.headers["X-RateLimit-Remaining"]) == ("3", "2")
    partner.get(f"{P}/watches")
    third = partner.get(f"{P}/watches")
    assert third.headers["X-RateLimit-Remaining"] == "0"

    blocked = partner.get(f"{P}/watches")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["Retry-After"]) >= 1

    # Limits are per key: another partner is unaffected.
    other_key = issue(admin_client, "Desert Cars Marketplace")["api_key"]
    with TestClient(app, base_url="https://testserver", headers={"X-API-Key": other_key}) as other:
        assert other.get(f"{P}/watches").status_code == 200


def test_key_guessing_is_throttled_too(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "partner_rate_limit", 2)
    with TestClient(app, base_url="https://testserver", headers={"X-API-Key": "sjl_00000000_guess"}) as guesser:
        codes = [guesser.get(f"{P}/watches").status_code for _ in range(4)]
    assert codes == [401, 401, 429, 429]


def test_rate_limiter_window_resets() -> None:
    now = [1000.0]
    limiter = RateLimiter(clock=lambda: now[0])
    assert [limiter.hit("k", 2, 60).allowed for _ in range(3)] == [True, True, False]
    assert limiter.hit("k", 2, 60).reset_after == 60
    now[0] += 60
    result = limiter.hit("k", 2, 60)
    assert result.allowed and result.remaining == 1


# --- documentation ---------------------------------------------------------------------------------


def test_partner_docs_list_the_six_endpoints(client: TestClient) -> None:
    spec = client.get(f"{P}/openapi.json").json()
    operations = sorted(f"{method.upper()} {path.removeprefix(P)}" for path, ops in spec["paths"].items() for method in ops)
    assert operations == [
        "DELETE /watches/{watch_id}", "GET /vehicles/{vin}", "GET /vehicles/{vin}/history",
        "GET /watches", "POST /watches", "PUT /watches/{watch_id}",
    ]
    assert "APIKeyHeader" in spec["components"]["securitySchemes"]
    assert not any("admin" in name.lower() or "user" in name.lower() for name in spec["components"]["schemas"])
    assert client.get(f"{P}/docs").status_code == 200


# --- demo key from the seed ------------------------------------------------------------------------


def test_seeded_demo_key_works_and_reseeding_is_safe(app: FastAPI, db: Session) -> None:
    from app.seed import seed_partner_key

    raw = "sjl_0a1b2c3d_" + "s" * 40
    first = seed_partner_key(db, raw)
    first.revoked_at = datetime.now(UTC)
    again = seed_partner_key(db, raw)  # idempotent, and revives a revoked demo key

    assert first.id == again.id and again.revoked_at is None
    assert db.scalar(select(func.count()).select_from(ApiKey)) == 1
    with TestClient(app, base_url="https://testserver", headers={"X-API-Key": raw}) as demo:
        assert demo.get(f"{P}/watches").status_code == 200
    for bad in ("sjl_short_" + "s" * 40, "sjl_0a1b2c3d_tooshort", "sjl_ZZZZZZZZ_" + "s" * 40):
        with pytest.raises(ValueError):
            seed_partner_key(db, bad)


def test_watching_a_vin_does_not_invent_a_history(client: TestClient, partner: TestClient) -> None:
    """Watching creates a vehicle row; the public timeline and partner summary still say "no history yet"."""
    partner.post(f"{P}/watches", json={"vin": "MDHBN7AD0P0012345"})

    timeline = client.get("/api/v1/vehicles/MDHBN7AD0P0012345/timeline").json()
    assert timeline["vehicle"] is None and timeline["records"] == []
    assert client.get("/api/v1/vehicles/MDHBN7AD0P0012345/report.pdf").status_code == 404
    assert partner.get(f"{P}/vehicles/MDHBN7AD0P0012345").json()["error"]["code"] == "vehicle_not_found"
