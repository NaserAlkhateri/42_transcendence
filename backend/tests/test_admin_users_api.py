import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    MemberRole,
    MemberStatus,
    OrganizationMember,
    ServiceRecord,
    User,
    UserRole,
    UserSession,
    UserStatus,
)
from tests.auth_helpers import add_member, add_user, csrf, login
from tests.factories import make_org, make_record, make_vehicle

USERS = "/api/v1/admin/users"


@pytest.fixture
def admin(client: TestClient, db: Session) -> User:
    """Signs `client` in as a platform admin."""
    user = add_user(db, "root@example.ae", full_name="Root Admin", role=UserRole.PLATFORM_ADMIN)
    login(client, user.email)
    return user


def other_client(app: FastAPI) -> TestClient:
    return TestClient(app, base_url="https://testserver")


# --- access control ---------------------------------------------------------------------------------


@pytest.mark.parametrize("member_role", [None, MemberRole.ENTITY_STAFF, MemberRole.ENTITY_ADMIN])
def test_only_platform_admins_reach_user_management(client: TestClient, db: Session, member_role) -> None:
    user = add_user(db, "someone@example.ae")
    if member_role:
        add_member(db, make_org(db), user, member_role)
    login(client, user.email)

    for response in (
        client.get(USERS),
        client.get(f"{USERS}/{user.id}"),
        client.patch(f"{USERS}/{user.id}", json={"role": "platform_admin"}, headers=csrf(client)),
        client.delete(f"{USERS}/{user.id}", headers=csrf(client)),
    ):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"
    assert db.get(User, user.id).role == UserRole.CONSUMER


def test_user_management_requires_sign_in(client: TestClient) -> None:
    assert client.get(USERS).status_code == 401


def test_admin_with_pending_temporary_password_is_blocked(client: TestClient, db: Session) -> None:
    add_user(db, "newadmin@example.ae", role=UserRole.PLATFORM_ADMIN, must_change=True)
    login(client, "newadmin@example.ae")
    assert client.get(USERS).json()["error"]["code"] == "password_change_required"


# --- read -------------------------------------------------------------------------------------------


def test_list_shows_effective_roles_and_memberships(client: TestClient, db: Session, admin: User) -> None:
    org = make_org(db, name="Falcon Test Garage")
    staff = add_user(db, "staff@example.ae")
    add_member(db, org, staff, MemberRole.ENTITY_STAFF)

    response = client.get(USERS, params={"page_size": 100})

    assert response.status_code == 200
    by_email = {item["email"]: item for item in response.json()["items"]}
    assert by_email["root@example.ae"]["effective_role"] == "platform_admin"
    assert by_email["staff@example.ae"]["effective_role"] == "entity_staff"
    assert by_email["staff@example.ae"]["memberships"][0]["organization_name"] == "Falcon Test Garage"
    assert "password_hash" not in by_email["staff@example.ae"]


def test_list_filters_by_role_status_and_search(client: TestClient, db: Session, admin: User) -> None:
    org = make_org(db)
    add_member(db, org, add_user(db, "boss@example.ae", full_name="Garage Boss"), MemberRole.ENTITY_ADMIN)
    add_member(db, org, add_user(db, "tech@example.ae", full_name="Garage Tech"), MemberRole.ENTITY_STAFF)
    add_user(db, "driver@example.ae", full_name="Plain Driver")
    add_user(db, "gone@example.ae", full_name="Disabled Driver", status=UserStatus.DISABLED)

    def emails(**params) -> set[str]:
        return {item["email"] for item in client.get(USERS, params={"page_size": 100, **params}).json()["items"]}

    assert emails(role="entity_admin") == {"boss@example.ae"}
    assert emails(role="entity_staff") == {"tech@example.ae"}
    assert {"driver@example.ae", "gone@example.ae"} <= emails(role="consumer")
    assert emails(role="consumer").isdisjoint({"boss@example.ae", "tech@example.ae", "root@example.ae"})
    assert emails(status="disabled") == {"gone@example.ae"}
    assert emails(q="garage") == {"boss@example.ae", "tech@example.ae"}
    assert emails(q="%") == set()  # wildcards are matched literally


def test_list_paginates(client: TestClient, db: Session, admin: User) -> None:
    for n in range(5):
        add_user(db, f"page{n}@example.ae", full_name="Paged User")

    first = client.get(USERS, params={"q": "Paged", "page_size": 2, "page": 1}).json()
    third = client.get(USERS, params={"q": "Paged", "page_size": 2, "page": 3}).json()

    assert first["total"] == 5 and len(first["items"]) == 2
    assert len(third["items"]) == 1
    assert client.get(USERS, params={"page_size": 101}).status_code == 422


def test_page_number_past_any_real_offset_is_rejected_not_a_server_error(client: TestClient, admin: User) -> None:
    # page=10**21 used to overflow the database OFFSET and answer 500.
    assert client.get(USERS, params={"page": 10**21}).status_code == 422


def test_get_unknown_user_is_404(client: TestClient, admin: User) -> None:
    response = client.get(f"{USERS}/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "user_not_found"


# --- update -----------------------------------------------------------------------------------------


def test_admin_edits_user_and_audit_records_the_change(client: TestClient, db: Session, admin: User) -> None:
    user = add_user(db, "edit@example.ae", full_name="Old Name")

    response = client.patch(
        f"{USERS}/{user.id}",
        json={"full_name": "New Name", "email": "Edited@Example.ae", "role": "platform_admin"},
        headers=csrf(client),
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["full_name"], body["email"], body["effective_role"]) == ("New Name", "edited@example.ae", "platform_admin")
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "user.updated"))
    assert event.actor_id == admin.id and event.target_id == str(user.id)
    assert event.details["changes"]["role"] == ["consumer", "platform_admin"]


def test_promoted_user_gains_admin_access_and_demoted_admin_loses_it(app: FastAPI, client: TestClient, db: Session, admin: User) -> None:
    user = add_user(db, "promote@example.ae")
    with other_client(app) as theirs:
        login(theirs, user.email)
        assert theirs.get(USERS).status_code == 403
        client.patch(f"{USERS}/{user.id}", json={"role": "platform_admin"}, headers=csrf(client))
        assert theirs.get(USERS).status_code == 200
        client.patch(f"{USERS}/{user.id}", json={"role": "consumer"}, headers=csrf(client))
        assert theirs.get(USERS).status_code == 403


def test_disabling_a_user_revokes_their_sessions(app: FastAPI, client: TestClient, db: Session, admin: User) -> None:
    user = add_user(db, "disable@example.ae")
    with other_client(app) as theirs:
        login(theirs, user.email)
        client.patch(f"{USERS}/{user.id}", json={"status": "disabled"}, headers=csrf(client))
        assert theirs.get("/api/v1/me").status_code == 401
        client.patch(f"{USERS}/{user.id}", json={"status": "active"}, headers=csrf(client))
        assert theirs.get("/api/v1/me").status_code == 401  # re-enabling does not revive old sessions
    live = db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)))
    assert live.all() == []


def test_admin_cannot_demote_or_disable_themselves(client: TestClient, admin: User) -> None:
    for change in ({"role": "consumer"}, {"status": "disabled"}):
        response = client.patch(f"{USERS}/{admin.id}", json=change, headers=csrf(client))
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "cannot_demote_self"
    assert client.patch(f"{USERS}/{admin.id}", json={"full_name": "Still Me"}, headers=csrf(client)).status_code == 200


def test_edit_validates_and_rejects_taken_email(client: TestClient, db: Session, admin: User) -> None:
    user = add_user(db, "mine@example.ae")
    add_user(db, "taken@example.ae")
    assert client.patch(f"{USERS}/{user.id}", json={"email": "taken@example.ae"}, headers=csrf(client)).status_code == 409
    assert client.patch(f"{USERS}/{user.id}", json={"role": "entity_admin"}, headers=csrf(client)).status_code == 422
    assert client.patch(f"{USERS}/{user.id}", json={"full_name": " "}, headers=csrf(client)).status_code == 422


def test_taken_email_is_a_conflict_even_when_the_same_edit_disables_the_user(client: TestClient, db: Session, admin: User) -> None:
    # Revoking sessions on disable used to autoflush the duplicate email outside the try and answer 500.
    user = add_user(db, "mine@example.ae")
    add_user(db, "taken@example.ae")

    response = client.patch(f"{USERS}/{user.id}", json={"email": "taken@example.ae", "status": "disabled"}, headers=csrf(client))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


def test_admin_changes_an_entity_role(client: TestClient, db: Session, admin: User) -> None:
    user = add_user(db, "member@example.ae")
    membership = add_member(db, make_org(db), user, MemberRole.ENTITY_STAFF)

    response = client.patch(
        f"{USERS}/{user.id}/memberships/{membership.id}", json={"role": "entity_admin"}, headers=csrf(client)
    )

    assert response.status_code == 200
    assert response.json()["effective_role"] == "entity_admin"
    assert db.get(OrganizationMember, membership.id).role == MemberRole.ENTITY_ADMIN
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "membership.role_changed")) is not None


def test_membership_must_belong_to_the_user_in_the_url(client: TestClient, db: Session, admin: User) -> None:
    owner = add_user(db, "owner@example.ae")
    someone_else = add_user(db, "else@example.ae")
    membership = add_member(db, make_org(db), owner, MemberRole.ENTITY_STAFF)
    response = client.patch(
        f"{USERS}/{someone_else.id}/memberships/{membership.id}", json={"role": "entity_admin"}, headers=csrf(client)
    )
    assert response.status_code == 404


def test_inactive_membership_does_not_grant_entity_role(client: TestClient, db: Session, admin: User) -> None:
    user = add_user(db, "former@example.ae")
    membership = add_member(db, make_org(db), user, MemberRole.ENTITY_ADMIN)
    membership.status = MemberStatus.INACTIVE
    db.flush()
    assert client.get(f"{USERS}/{user.id}").json()["effective_role"] == "consumer"


# --- delete -----------------------------------------------------------------------------------------


def test_delete_really_removes_the_user_but_keeps_history(app: FastAPI, client: TestClient, db: Session, admin: User) -> None:
    org = make_org(db)
    staff = add_user(db, "leaver@example.ae", full_name="Leaving Technician")
    membership = add_member(db, org, staff, MemberRole.ENTITY_STAFF)
    record = make_record(db, make_vehicle(db), org, staff)
    staff_id, membership_id, record_id = staff.id, membership.id, record.id
    with other_client(app) as theirs:
        login(theirs, staff.email)

        response = client.delete(f"{USERS}/{staff_id}", headers=csrf(client))

        assert response.status_code == 204
        assert theirs.get("/api/v1/me").status_code == 401
    db.expunge_all()  # read back from the database, not the identity map
    assert db.get(User, staff_id) is None
    assert db.get(OrganizationMember, membership_id) is None
    assert db.scalars(select(UserSession).where(UserSession.user_id == staff_id)).all() == []
    kept = db.get(ServiceRecord, record_id)
    assert kept.staff_id is None and kept.staff_name == "Leaving Technician"
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "user.deleted"))
    assert event.details["email"] == "leaver@example.ae" and event.actor_label == "root@example.ae"
    assert client.get(f"{USERS}/{staff_id}").status_code == 404


def test_admin_cannot_delete_themselves(client: TestClient, admin: User) -> None:
    response = client.delete(f"{USERS}/{admin.id}", headers=csrf(client))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cannot_delete_self"


def test_delete_requires_csrf(client: TestClient, db: Session, admin: User) -> None:
    user = add_user(db, "csrf-victim@example.ae")
    assert client.delete(f"{USERS}/{user.id}").status_code == 403
    assert db.get(User, user.id) is not None
