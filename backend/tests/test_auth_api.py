from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import MemberRole, User, UserRole, UserSession, UserStatus
from tests.auth_helpers import PASSWORD, add_member, add_user, csrf, login
from tests.factories import make_org


def signup(client: TestClient, email: str = "Layla@Example.ae", **overrides: str):
    body = {"email": email, "password": PASSWORD, "full_name": "Layla Hassan", **overrides}
    return client.post("/api/v1/auth/signup", json=body, headers=csrf(client))


def set_cookie_header(response, name: str) -> str:
    return next(h for h in response.headers.get_list("set-cookie") if h.startswith(f"{name}="))


# --- signup -----------------------------------------------------------------------------------------


def test_signup_creates_consumer_with_argon2id_hash_and_signs_in(client: TestClient, db: Session) -> None:
    response = signup(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "layla@example.ae"
    assert body["role"] == "consumer"
    assert "password_hash" not in body
    stored = db.scalar(select(User).where(User.email == "layla@example.ae"))
    assert stored.password_hash.startswith("$argon2id$")
    assert PASSWORD not in stored.password_hash
    assert client.get("/api/v1/me").json()["email"] == "layla@example.ae"


def test_session_cookie_is_httponly_secure_samesite(client: TestClient) -> None:
    cookie = set_cookie_header(signup(client), "sijil_session").lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie


def test_session_token_is_stored_hashed(client: TestClient, db: Session) -> None:
    signup(client)
    token = client.cookies["sijil_session"]
    hashes = db.scalars(select(UserSession.token_hash)).all()
    assert hashes and token not in hashes


def test_signup_cannot_choose_a_role(client: TestClient) -> None:
    response = signup(client, role="platform_admin")
    assert response.status_code == 201
    assert response.json()["role"] == UserRole.CONSUMER


def test_duplicate_email_is_rejected_case_insensitively(client: TestClient) -> None:
    assert signup(client, "sara@example.ae").status_code == 201
    response = signup(client, "SARA@example.AE")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


def test_signup_validates_input(client: TestClient) -> None:
    assert signup(client, "not-an-email").status_code == 422
    assert signup(client, "a@example.ae", password="short").status_code == 422
    assert signup(client, "b@example.ae", password="x" * 129).status_code == 422
    response = signup(client, "c@example.ae", full_name="   ")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# --- CSRF -------------------------------------------------------------------------------------------


def test_state_changing_request_without_csrf_header_is_refused(client: TestClient) -> None:
    client.get("/api/v1/auth/csrf")
    body = {"email": "x@example.ae", "password": PASSWORD, "full_name": "X"}

    missing = client.post("/api/v1/auth/signup", json=body)
    wrong = client.post("/api/v1/auth/signup", json=body, headers={"X-CSRF-Token": "forged"})

    for response in (missing, wrong):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "csrf_failed"


def test_csrf_token_rotates_on_login(client: TestClient, db: Session) -> None:
    add_user(db, "rotate@example.ae")
    before = csrf(client)["X-CSRF-Token"]
    login(client, "rotate@example.ae")
    assert client.cookies["sijil_csrf"] != before


# --- login / logout ---------------------------------------------------------------------------------


def test_login_with_correct_password(client: TestClient, db: Session) -> None:
    add_user(db, "omar@example.ae")
    response = login(client, "Omar@Example.ae")
    assert response.status_code == 200
    assert response.json()["email"] == "omar@example.ae"
    assert client.get("/api/v1/me").status_code == 200


def test_login_failures_share_one_generic_answer(client: TestClient, db: Session) -> None:
    add_user(db, "known@example.ae")
    add_user(db, "disabled@example.ae", status=UserStatus.DISABLED)

    wrong_password = login(client, "known@example.ae", "wrong-password-1")
    unknown_email = login(client, "nobody@example.ae")
    disabled = login(client, "disabled@example.ae")

    for response in (wrong_password, unknown_email, disabled):
        assert response.status_code == 401
        assert response.json() == {
            "error": {"code": "invalid_credentials", "message": "Email or password is incorrect."}
        }


def test_logout_revokes_the_session_server_side(client: TestClient) -> None:
    signup(client)
    token = client.cookies["sijil_session"]

    assert client.post("/api/v1/auth/logout", headers=csrf(client)).status_code == 204
    assert "sijil_session" not in client.cookies
    replay = client.get("/api/v1/me", headers={"Cookie": f"sijil_session={token}"})
    assert replay.status_code == 401


def test_logout_when_signed_out_is_harmless(client: TestClient) -> None:
    assert client.post("/api/v1/auth/logout", headers=csrf(client)).status_code == 204


def test_expired_session_is_rejected(client: TestClient, db: Session) -> None:
    signup(client)
    db.execute(update(UserSession).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    assert client.get("/api/v1/me").status_code == 401


def test_disabling_a_user_ends_their_sessions(client: TestClient, db: Session) -> None:
    user = add_user(db, "later-disabled@example.ae")
    login(client, "later-disabled@example.ae")
    user.status = UserStatus.DISABLED
    db.flush()
    assert client.get("/api/v1/me").status_code == 401


def test_session_probe_answers_200_with_no_user_when_signed_out(client: TestClient) -> None:
    # The SPA calls this on every page load; a 401 here would print an error in every visitor's console.
    response = client.get("/api/v1/auth/session")
    assert response.status_code == 200
    assert response.json() == {"user": None}


def test_session_probe_returns_the_signed_in_user(client: TestClient) -> None:
    signup(client)
    response = client.get("/api/v1/auth/session")
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "layla@example.ae"


def test_session_probe_treats_an_expired_session_as_signed_out(client: TestClient, db: Session) -> None:
    signup(client)
    db.execute(update(UserSession).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    assert client.get("/api/v1/auth/session").json() == {"user": None}


def test_me_requires_a_session(client: TestClient) -> None:
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_two_users_signed_in_at_once_each_see_their_own_profile(app: FastAPI, db: Session) -> None:
    add_user(db, "first@example.ae")
    add_user(db, "second@example.ae")
    with (
        TestClient(app, base_url="https://testserver") as first,
        TestClient(app, base_url="https://testserver") as second,
    ):
        login(first, "first@example.ae")
        login(second, "second@example.ae")
        assert first.get("/api/v1/me").json()["email"] == "first@example.ae"
        assert second.get("/api/v1/me").json()["email"] == "second@example.ae"


# --- profile and password ---------------------------------------------------------------------------


def test_update_profile_name(client: TestClient) -> None:
    signup(client)
    response = client.patch("/api/v1/me", json={"full_name": "  Layla H.  "}, headers=csrf(client))
    assert response.status_code == 200
    assert response.json()["full_name"] == "Layla H."
    assert client.patch("/api/v1/me", json={"full_name": ""}, headers=csrf(client)).status_code == 422


def test_change_password_signs_out_other_devices(app: FastAPI, client: TestClient, db: Session) -> None:
    add_user(db, "pw@example.ae")
    login(client, "pw@example.ae")
    with TestClient(app, base_url="https://testserver") as other_device:
        login(other_device, "pw@example.ae")

        new_password = "a-brand-new-passphrase"
        response = client.post(
            "/api/v1/me/password",
            json={"current_password": PASSWORD, "new_password": new_password},
            headers=csrf(client),
        )

        assert response.status_code == 204
        assert client.get("/api/v1/me").status_code == 200
        assert other_device.get("/api/v1/me").status_code == 401
    assert login(client, "pw@example.ae").status_code == 401
    assert login(client, "pw@example.ae", new_password).status_code == 200


def test_change_password_checks_current_password(client: TestClient) -> None:
    signup(client)
    wrong = client.post(
        "/api/v1/me/password",
        json={"current_password": "not-my-password", "new_password": "another-long-one"},
        headers=csrf(client),
    )
    same = client.post(
        "/api/v1/me/password", json={"current_password": PASSWORD, "new_password": PASSWORD}, headers=csrf(client)
    )
    assert wrong.json()["error"]["code"] == "invalid_current_password"
    assert same.json()["error"]["code"] == "password_unchanged"


def test_temporary_password_must_be_changed_before_other_actions(client: TestClient, db: Session) -> None:
    add_user(db, "staff@example.ae", must_change=True)
    login(client, "staff@example.ae")

    assert client.get("/api/v1/me").json()["must_change_password"] is True
    blocked = client.patch("/api/v1/me", json={"full_name": "New"}, headers=csrf(client))
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "password_change_required"

    client.post(
        "/api/v1/me/password",
        json={"current_password": PASSWORD, "new_password": "my-own-password-now"},
        headers=csrf(client),
    )
    assert client.patch("/api/v1/me", json={"full_name": "New"}, headers=csrf(client)).status_code == 200


def test_me_reports_effective_role_and_memberships(client: TestClient, db: Session) -> None:
    user = add_user(db, "tech@example.ae")
    add_member(db, make_org(db, name="Me Garage"), user, MemberRole.ENTITY_STAFF)
    login(client, user.email)

    body = client.get("/api/v1/me").json()

    assert body["role"] == "consumer"
    assert body["effective_role"] == "entity_staff"
    assert [(m["organization_name"], m["role"]) for m in body["memberships"]] == [("Me Garage", "entity_staff")]
