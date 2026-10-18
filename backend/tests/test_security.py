"""NA-06 hardening: throttling, session rotation, the last-admin lock, admin password resets, HTTP headers,
request size limit and the error shape for unexpected failures."""

import threading
import time
import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.api.v1 import admin_users
from app.auth.passwords import hash_password
from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app
from app.models import AuditEvent, MemberRole, User, UserRole, UserStatus
from tests.auth_helpers import PASSWORD, add_member, add_user, csrf, login
from tests.factories import make_org


def other_client(app: FastAPI) -> TestClient:
    return TestClient(app, base_url="https://testserver")


# --- login, signup and password throttling --------------------------------------------------------


def test_login_attempts_are_limited_per_ip(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "login_attempts_per_ip", 3)
    add_user(db, "omar@example.ae")
    codes = [login(client, "omar@example.ae", "wrong-password-1").status_code for _ in range(3)]
    blocked = login(client, "omar@example.ae")  # even the right password waits for the window
    assert codes == [401, 401, 401]
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["Retry-After"]) >= 1


def test_failed_logins_lock_the_email_not_the_person_next_to_you(
    app: FastAPI, client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "login_failures_per_email", 3)
    add_user(db, "target@example.ae")
    add_user(db, "bystander@example.ae")
    for _ in range(3):
        assert login(client, "target@example.ae", "guess-guess-guess").status_code == 401

    assert login(client, "target@example.ae").status_code == 429  # locked, right password or not
    with other_client(app) as elsewhere:
        assert login(elsewhere, "TARGET@example.ae").status_code == 429  # the lock follows the email
        assert login(elsewhere, "bystander@example.ae").status_code == 200


def test_unknown_emails_lock_the_same_way(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 for a made-up email too, so the lock can't be used to discover which emails exist."""
    monkeypatch.setattr(get_settings(), "login_failures_per_email", 2)
    codes = [login(client, "nobody@example.ae", "whatever-whatever").status_code for _ in range(3)]
    assert codes == [401, 401, 429]


def test_a_successful_login_clears_earlier_failures(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "login_failures_per_email", 3)
    add_user(db, "typo@example.ae")
    login(client, "typo@example.ae", "wrong-password-1")
    login(client, "typo@example.ae", "wrong-password-2")
    assert login(client, "typo@example.ae").status_code == 200
    for _ in range(2):
        assert login(client, "typo@example.ae", "wrong-password-3").status_code == 401  # counter started again


def test_signups_are_limited_per_ip(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "signups_per_ip", 2)

    def signup(n: int):
        body = {"email": f"new{n}@example.ae", "password": PASSWORD, "full_name": "New Person"}
        return client.post("/api/v1/auth/signup", json=body, headers=csrf(client))

    assert [signup(1).status_code, signup(2).status_code, signup(3).status_code] == [201, 201, 429]


def test_wrong_current_passwords_are_limited(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "password_failures_per_user", 2)
    add_user(db, "pw@example.ae")
    login(client, "pw@example.ae")

    def change(current: str):
        return client.post("/api/v1/me/password", json={"current_password": current, "new_password": "a-new-passphrase"},
                           headers=csrf(client))

    assert [change("wrong-1").status_code, change("wrong-2").status_code] == [400, 400]
    assert change(PASSWORD).status_code == 429


# --- sessions --------------------------------------------------------------------------------------


def test_password_change_issues_a_new_session(client: TestClient, db: Session) -> None:
    user = add_user(db, "rotate@example.ae")
    login(client, user.email)
    old_token = client.cookies["sijil_session"]

    response = client.post("/api/v1/me/password", headers=csrf(client),
                           json={"current_password": PASSWORD, "new_password": "rotated-passphrase"})

    assert response.status_code == 204
    assert client.cookies["sijil_session"] != old_token
    assert client.get("/api/v1/me").status_code == 200  # this browser carries on with the new session
    replay = client.get("/api/v1/me", headers={"Cookie": f"sijil_session={old_token}"})
    assert replay.status_code == 401
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "user.password_changed"))
    assert event.actor_id == user.id and "rotated-passphrase" not in str(event.details)


def test_signing_in_again_ends_the_previous_session(client: TestClient, db: Session) -> None:
    add_user(db, "again@example.ae")
    login(client, "again@example.ae")
    first = client.cookies["sijil_session"]
    login(client, "again@example.ae")
    assert client.cookies["sijil_session"] != first
    assert client.get("/api/v1/me", headers={"Cookie": f"sijil_session={first}"}).status_code == 401


def test_own_name_change_is_audited(client: TestClient, db: Session) -> None:
    add_user(db, "name@example.ae", full_name="Old Name")
    login(client, "name@example.ae")
    client.patch("/api/v1/me", json={"full_name": "New Name"}, headers=csrf(client))
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "user.profile_updated"))
    assert event.details == {"changes": {"full_name": ["Old Name", "New Name"]}}


# --- platform admins -------------------------------------------------------------------------------


@pytest.fixture
def admin_client(app: FastAPI, db: Session) -> Iterator[TestClient]:
    add_user(db, "root@example.ae", role=UserRole.PLATFORM_ADMIN)
    with other_client(app) as admin:
        login(admin, "root@example.ae")
        yield admin


def test_admin_resets_a_forgotten_password(app: FastAPI, db: Session, admin_client: TestClient) -> None:
    staff = add_user(db, "forgot@example.ae")
    with other_client(app) as old_device:
        login(old_device, staff.email)

        response = admin_client.post(f"/api/v1/admin/users/{staff.id}/reset-password", headers=csrf(admin_client))

        assert response.status_code == 200
        temporary = response.json()["temporary_password"]
        assert old_device.get("/api/v1/me").status_code == 401  # every session ended
    db.refresh(staff)
    assert staff.must_change_password and temporary not in staff.password_hash
    with other_client(app) as fresh:
        assert login(fresh, staff.email, temporary).status_code == 200
        assert fresh.get("/api/v1/me").json()["must_change_password"] is True
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "user.password_reset"))
    assert temporary not in str(event.details)


def test_password_reset_is_for_platform_admins_only(client: TestClient, db: Session, admin_client: TestClient) -> None:
    org = make_org(db)
    boss, staff = add_user(db, "boss@example.ae"), add_user(db, "tech@example.ae")
    add_member(db, org, boss, MemberRole.ENTITY_ADMIN)
    add_member(db, org, staff, MemberRole.ENTITY_STAFF)
    login(client, boss.email)
    assert client.post(f"/api/v1/admin/users/{staff.id}/reset-password", headers=csrf(client)).status_code == 403
    me = admin_client.get("/api/v1/me").json()["id"]
    assert admin_client.post(f"/api/v1/admin/users/{me}/reset-password", headers=csrf(admin_client)).json()["error"]["code"] == "cannot_reset_self"


def test_deleting_a_user_records_their_memberships(db: Session, admin_client: TestClient) -> None:
    org = make_org(db, name="Audit Garage")
    staff = add_user(db, "leaver@example.ae")
    add_member(db, org, staff, MemberRole.ENTITY_STAFF)
    admin_client.delete(f"/api/v1/admin/users/{staff.id}", headers=csrf(admin_client))
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "user.deleted"))
    assert event.details["memberships"] == [
        {"organization_id": str(org.id), "organization_name": "Audit Garage", "role": "entity_staff", "status": "active"}
    ]


@pytest.fixture
def two_committed_admins(engine: Engine) -> Iterator[tuple[str, str]]:
    """Committed rows: each concurrent request needs its own connection, so these can't live in the
    rolled-back test transaction. Removed afterwards."""
    tag = uuid.uuid4().hex[:8]
    emails = (f"admin-a.{tag}@example.ae", f"admin-b.{tag}@example.ae")
    with Session(engine) as session:
        for email in emails:
            session.add(User(email=email, password_hash=hash_password(PASSWORD), full_name="Race Admin",
                             role=UserRole.PLATFORM_ADMIN))
        session.commit()
    yield emails
    with Session(engine) as session:
        ids = session.scalars(select(User.id).where(User.email.in_(emails))).all()
        session.execute(delete(AuditEvent).where(AuditEvent.target_id.in_([str(i) for i in ids])))
        session.execute(delete(User).where(User.id.in_(ids)))
        session.commit()


def test_two_admins_demoting_each_other_at_once_leaves_one(
    engine: Engine, two_committed_admins: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app()

    def real_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = real_db
    # Hold each request inside its admin check, so without the row lock both would see two admins and pass.
    check = admin_users._require_another_platform_admin

    def slow_check(db: Session, user: User) -> None:
        check(db, user)
        time.sleep(0.4)

    monkeypatch.setattr(admin_users, "_require_another_platform_admin", slow_check)
    clients = [TestClient(app, base_url="https://testserver") for _ in two_committed_admins]
    ids = []
    for c, email in zip(clients, two_committed_admins, strict=True):
        login(c, email)
        ids.append(c.get("/api/v1/me").json()["id"])

    start = threading.Barrier(2)
    codes: dict[int, int] = {}

    def demote(i: int) -> None:
        start.wait()
        other = ids[1 - i]
        codes[i] = clients[i].patch(f"/api/v1/admin/users/{other}", json={"role": "consumer"},
                                    headers=csrf(clients[i])).status_code

    threads = [threading.Thread(target=demote, args=(i,)) for i in (0, 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for c in clients:
        c.close()

    assert sorted(codes.values()) == [200, 409]
    with Session(engine) as session:
        remaining = session.scalars(
            select(User).where(User.email.in_(two_committed_admins), User.role == UserRole.PLATFORM_ADMIN,
                               User.status == UserStatus.ACTIVE)
        ).all()
    assert len(remaining) == 1


# --- HTTP hardening --------------------------------------------------------------------------------


def test_api_responses_carry_security_headers(client: TestClient) -> None:
    response = client.get("/api/v1/auth/session")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert response.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")


def test_docs_pages_keep_working(client: TestClient) -> None:
    docs = client.get("/api/v1/docs")
    assert docs.status_code == 200 and "Content-Security-Policy" not in docs.headers


def test_oversized_bodies_are_refused(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "max_request_bytes", 1_000)
    response = client.post("/api/v1/auth/login", content=b"x" * 2_000, headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_unexpected_errors_use_the_error_shape_without_details(db: Session) -> None:
    app = create_app()

    @app.get("/api/v1/boom")
    def boom() -> None:
        raise RuntimeError("database password is hunter2")

    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as c:
        response = c.get("/api/v1/boom")
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "internal_error", "message": "Something went wrong on our side."}}
    assert "hunter2" not in response.text
