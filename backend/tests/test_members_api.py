import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    MemberRole,
    MemberStatus,
    Organization,
    OrganizationMember,
    OrganizationStatus,
    ServiceRecord,
    User,
    UserRole,
)
from app.services import events
from tests.auth_helpers import add_member, add_user, csrf, login
from tests.factories import make_org, make_record, make_vehicle

RECORD = {"vin": "JTMHX01J5M4012345", "service_date": "2026-01-10", "category": "maintenance",
          "work_codes": ["OIL_CHANGE"], "odometer_km": 42_000}


def members_url(org: Organization) -> str:
    return f"/api/v1/organizations/{org.id}/members"


def other_client(app: FastAPI) -> TestClient:
    return TestClient(app, base_url="https://testserver")


@pytest.fixture
def org(db: Session) -> Organization:
    return make_org(db, name="Falcon Test Garage")


@pytest.fixture
def boss(client: TestClient, db: Session, org: Organization) -> OrganizationMember:
    """Signs `client` in as the organization's only entity admin."""
    user = add_user(db, "boss@example.ae", full_name="Hamad Al Ketbi")
    membership = add_member(db, org, user, MemberRole.ENTITY_ADMIN)
    login(client, user.email)
    return membership


@pytest.fixture
def published() -> list[tuple[str, dict]]:
    received: list[tuple[str, dict]] = []
    unsubscribe = events.subscribe(lambda event_type, payload: received.append((event_type, payload)))
    yield received
    unsubscribe()


# --- who can manage members ------------------------------------------------------------------------


def test_entity_admin_lists_members(client: TestClient, db: Session, org: Organization, boss: OrganizationMember) -> None:
    add_member(db, org, add_user(db, "tech@example.ae", full_name="Arjun Nair"), MemberRole.ENTITY_STAFF)
    response = client.get(members_url(org))
    assert response.status_code == 200
    assert {(m["full_name"], m["role"]) for m in response.json()} == {
        ("Hamad Al Ketbi", "entity_admin"), ("Arjun Nair", "entity_staff"),
    }


def test_staff_outsiders_and_other_organizations_cannot_manage(app: FastAPI, db: Session, org: Organization) -> None:
    other_org = make_org(db, name="Other Garage")
    staff = add_user(db, "tech@example.ae")
    add_member(db, org, staff, MemberRole.ENTITY_STAFF)
    other_boss = add_user(db, "otherboss@example.ae")
    add_member(db, other_org, other_boss, MemberRole.ENTITY_ADMIN)
    add_user(db, "outsider@example.ae")

    for email in ("tech@example.ae", "otherboss@example.ae", "outsider@example.ae"):
        with other_client(app) as c:
            login(c, email)
            assert c.get(members_url(org)).status_code == 403
            response = c.post(members_url(org), json={"email": "outsider@example.ae", "role": "entity_admin"}, headers=csrf(c))
            assert response.status_code == 403, email
            assert c.post(f"{members_url(org)}/staff-accounts", json={"email": "x@example.ae", "full_name": "X"},
                          headers=csrf(c)).status_code == 403


# --- adding an existing account --------------------------------------------------------------------


def test_add_existing_account(
    app: FastAPI, client: TestClient, db: Session, org: Organization, boss: OrganizationMember, published: list
) -> None:
    newcomer = add_user(db, "sara@example.ae", full_name="Sara Haddad")

    response = client.post(members_url(org), json={"email": "Sara@Example.ae", "role": "entity_staff"}, headers=csrf(client))

    assert response.status_code == 201
    assert (response.json()["full_name"], response.json()["role"]) == ("Sara Haddad", "entity_staff")
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "membership.added")) is not None
    assert published[-1] == ("membership.added", {
        "organization_id": str(org.id), "organization_name": "Falcon Test Garage", "user_id": str(newcomer.id),
        "role": "entity_staff", "status": "active",
    })
    with other_client(app) as sara:
        login(sara, "sara@example.ae")
        assert sara.get("/api/v1/me").json()["effective_role"] == "entity_staff"
        assert sara.post(f"/api/v1/organizations/{org.id}/records", json=RECORD, headers=csrf(sara)).status_code == 201


def test_add_existing_account_refusals(client: TestClient, db: Session, org: Organization, boss: OrganizationMember) -> None:
    add_user(db, "admin@example.ae", role=UserRole.PLATFORM_ADMIN)

    def add(email: str):
        return client.post(members_url(org), json={"email": email, "role": "entity_staff"}, headers=csrf(client))

    assert add("nobody@example.ae").json()["error"]["code"] == "user_not_found"
    assert add("boss@example.ae").json()["error"]["code"] == "already_member"
    assert add("admin@example.ae").json()["error"]["code"] == "cannot_add_platform_admin"
    assert add("not-an-email").status_code == 422
    bad_role = client.post(members_url(org), json={"email": "boss@example.ae", "role": "platform_admin"}, headers=csrf(client))
    assert bad_role.status_code == 422  # entity roles only: no one grants a platform role here


def test_unapproved_organizations_cannot_onboard(client: TestClient, db: Session) -> None:
    pending = make_org(db, name="Pending Garage", status=OrganizationStatus.PENDING)
    add_member(db, pending, add_user(db, "applicant@example.ae"), MemberRole.ENTITY_ADMIN)
    add_user(db, "friend@example.ae")
    login(client, "applicant@example.ae")

    added = client.post(members_url(pending), json={"email": "friend@example.ae", "role": "entity_staff"}, headers=csrf(client))
    created = client.post(f"{members_url(pending)}/staff-accounts", json={"email": "new@example.ae", "full_name": "New"},
                          headers=csrf(client))

    for response in (added, created):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "organization_not_approved"
    assert db.scalar(select(User).where(User.email == "new@example.ae")) is None


def test_platform_admin_staffs_an_organization_it_created(client: TestClient, db: Session) -> None:
    add_user(db, "root@example.ae", role=UserRole.PLATFORM_ADMIN)
    add_user(db, "manager@example.ae")
    login(client, "root@example.ae")
    created = client.post("/api/v1/admin/organizations", headers=csrf(client), json={
        "name": "Oasis Test Motors", "kind": "dealership", "registration_number": "AUH-55", "emirate": "Abu Dhabi",
    }).json()

    response = client.post(f"/api/v1/organizations/{created['id']}/members",
                           json={"email": "manager@example.ae", "role": "entity_admin"}, headers=csrf(client))

    assert response.status_code == 201
    detail = client.get(f"/api/v1/admin/organizations/{created['id']}").json()
    assert [(m["email"], m["role"]) for m in detail["members"]] == [("manager@example.ae", "entity_admin")]


# --- staff accounts with a temporary password -------------------------------------------------------


def test_staff_account_must_replace_its_temporary_password(
    app: FastAPI, client: TestClient, db: Session, org: Organization, boss: OrganizationMember
) -> None:
    response = client.post(f"{members_url(org)}/staff-accounts", headers=csrf(client),
                           json={"email": "Arjun@Example.ae", "full_name": "Arjun Nair", "role": "entity_staff"})

    assert response.status_code == 201
    body = response.json()
    temporary = body["temporary_password"]
    assert len(temporary) >= 16 and body["member"]["email"] == "arjun@example.ae"
    stored = db.scalar(select(User).where(User.email == "arjun@example.ae"))
    assert stored.must_change_password and stored.role == UserRole.CONSUMER
    assert temporary not in stored.password_hash and stored.password_hash.startswith("$argon2id$")
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "membership.staff_account_created")) is not None
    assert "temporary_password" not in str(db.scalars(select(AuditEvent.details)).all())

    with other_client(app) as arjun:
        assert login(arjun, "arjun@example.ae", temporary).status_code == 200
        assert arjun.get("/api/v1/me").json()["must_change_password"] is True
        blocked = arjun.post(f"/api/v1/organizations/{org.id}/records", json=RECORD, headers=csrf(arjun))
        assert blocked.json()["error"]["code"] == "password_change_required"

        changed = arjun.post("/api/v1/me/password", headers=csrf(arjun),
                             json={"current_password": temporary, "new_password": "arjun-own-passphrase"})
        assert changed.status_code == 204
        assert arjun.post(f"/api/v1/organizations/{org.id}/records", json=RECORD, headers=csrf(arjun)).status_code == 201


def test_staff_account_email_must_be_new(client: TestClient, db: Session, org: Organization, boss: OrganizationMember) -> None:
    add_user(db, "taken@example.ae")
    response = client.post(f"{members_url(org)}/staff-accounts", json={"email": "taken@example.ae", "full_name": "T"},
                           headers=csrf(client))
    assert response.status_code == 409 and response.json()["error"]["code"] == "email_taken"
    blank = client.post(f"{members_url(org)}/staff-accounts", json={"email": "ok@example.ae", "full_name": " "},
                        headers=csrf(client))
    assert blank.status_code == 422


# --- roles and status ------------------------------------------------------------------------------


def test_promote_demote_and_deactivate(app: FastAPI, client: TestClient, db: Session, org: Organization, boss: OrganizationMember) -> None:
    tech = add_user(db, "tech@example.ae")
    membership = add_member(db, org, tech, MemberRole.ENTITY_STAFF)
    url = f"{members_url(org)}/{membership.id}"

    assert client.patch(url, json={"role": "entity_admin"}, headers=csrf(client)).json()["role"] == "entity_admin"
    assert client.patch(url, json={"role": "entity_staff"}, headers=csrf(client)).json()["role"] == "entity_staff"
    deactivated = client.patch(url, json={"status": "inactive"}, headers=csrf(client))

    assert deactivated.json()["status"] == "inactive"
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "membership.updated")).all()[-1]
    assert event.details["changes"] == {"status": ["active", "inactive"]}
    with other_client(app) as c:
        login(c, tech.email)
        assert c.get("/api/v1/me").json()["effective_role"] == "consumer"
        assert c.post(f"/api/v1/organizations/{org.id}/records", json=RECORD, headers=csrf(c)).status_code == 403


def test_organization_keeps_one_active_entity_admin(client: TestClient, db: Session, org: Organization, boss: OrganizationMember) -> None:
    url = f"{members_url(org)}/{boss.id}"
    for change in ({"role": "entity_staff"}, {"status": "inactive"}):
        response = client.patch(url, json=change, headers=csrf(client))
        assert response.status_code == 409 and response.json()["error"]["code"] == "last_entity_admin"
    assert client.delete(url, headers=csrf(client)).json()["error"]["code"] == "last_entity_admin"

    # With a second admin, the first may step down.
    add_member(db, org, add_user(db, "deputy@example.ae"), MemberRole.ENTITY_ADMIN)
    assert client.patch(url, json={"role": "entity_staff"}, headers=csrf(client)).status_code == 200


def test_platform_admin_role_endpoint_also_keeps_one_admin(app: FastAPI, db: Session, org: Organization, boss: OrganizationMember) -> None:
    add_user(db, "root@example.ae", role=UserRole.PLATFORM_ADMIN)
    with other_client(app) as root:
        login(root, "root@example.ae")
        response = root.patch(f"/api/v1/admin/users/{boss.user_id}/memberships/{boss.id}", json={"role": "entity_staff"},
                              headers=csrf(root))
    assert response.status_code == 409 and response.json()["error"]["code"] == "last_entity_admin"


def test_membership_must_belong_to_the_organization_in_the_url(client: TestClient, db: Session, org: Organization, boss: OrganizationMember) -> None:
    elsewhere = add_member(db, make_org(db, name="Elsewhere"), add_user(db, "x@example.ae"), MemberRole.ENTITY_STAFF)
    assert client.patch(f"{members_url(org)}/{elsewhere.id}", json={"role": "entity_admin"}, headers=csrf(client)).status_code == 404
    assert client.delete(f"{members_url(org)}/{elsewhere.id}", headers=csrf(client)).status_code == 404
    assert db.get(OrganizationMember, elsewhere.id).role == MemberRole.ENTITY_STAFF


# --- removing --------------------------------------------------------------------------------------


def test_remove_member_keeps_their_account_and_history(
    app: FastAPI, client: TestClient, db: Session, org: Organization, boss: OrganizationMember, published: list
) -> None:
    leaver = add_user(db, "leaver@example.ae", full_name="Leaving Technician")
    membership = add_member(db, org, leaver, MemberRole.ENTITY_STAFF)
    record = make_record(db, make_vehicle(db), org, leaver)
    membership_id, record_id, leaver_id = membership.id, record.id, leaver.id

    response = client.delete(f"{members_url(org)}/{membership_id}", headers=csrf(client))

    assert response.status_code == 204
    db.expunge_all()
    assert db.get(OrganizationMember, membership_id) is None
    assert db.get(User, leaver_id) is not None
    assert db.get(ServiceRecord, record_id).staff_name == "Leaving Technician"
    assert published[-1][0] == "membership.removed"
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "membership.removed"))
    assert event.details["email"] == "leaver@example.ae"
    with other_client(app) as c:
        login(c, "leaver@example.ae")
        assert c.get("/api/v1/me").json()["memberships"] == []


def test_member_writes_need_csrf(client: TestClient, db: Session, org: Organization, boss: OrganizationMember) -> None:
    membership = add_member(db, org, add_user(db, "tech@example.ae"), MemberRole.ENTITY_STAFF)
    assert client.delete(f"{members_url(org)}/{membership.id}").status_code == 403
    assert db.get(OrganizationMember, membership.id).status == MemberStatus.ACTIVE
