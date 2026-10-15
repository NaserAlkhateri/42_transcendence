import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    MemberRole,
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

ORGS = "/api/v1/organizations"
ADMIN_ORGS = "/api/v1/admin/organizations"
VIN = "JTMHX01J5M4012345"


def registration(**overrides) -> dict:
    return {
        "name": "Corniche Tyre Centre", "kind": "workshop", "registration_number": "dxb-778899", "emirate": "Dubai",
        **overrides,
    }


def record_body() -> dict:
    return {"vin": VIN, "service_date": "2026-01-10", "category": "maintenance", "work_codes": ["OIL_CHANGE"], "odometer_km": 42_000}


def other_client(app: FastAPI) -> TestClient:
    return TestClient(app, base_url="https://testserver")


@pytest.fixture
def applicant(client: TestClient, db: Session) -> User:
    """Signs `client` in as a consumer who is about to register a business."""
    user = add_user(db, "owner@example.ae", full_name="Mariam Al Mansoori")
    login(client, user.email)
    return user


@pytest.fixture
def admin_client(app: FastAPI, db: Session):
    add_user(db, "root@example.ae", full_name="Root Admin", role=UserRole.PLATFORM_ADMIN)
    with other_client(app) as admin:
        login(admin, "root@example.ae")
        yield admin


@pytest.fixture
def published() -> list[tuple[str, dict]]:
    received: list[tuple[str, dict]] = []
    unsubscribe = events.subscribe(lambda event_type, payload: received.append((event_type, payload)))
    yield received
    unsubscribe()


# --- registration (member side) ---------------------------------------------------------------------


def test_registration_creates_a_pending_organization_run_by_the_applicant(client: TestClient, db: Session, applicant: User) -> None:
    response = client.post(ORGS, json=registration(), headers=csrf(client))

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["registration_number"] == "DXB-778899"  # stored upper-case
    membership = db.scalar(select(OrganizationMember).where(OrganizationMember.user_id == applicant.id))
    assert membership.role == MemberRole.ENTITY_ADMIN and str(membership.organization_id) == body["id"]
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "organization.registered")) is not None

    me = client.get("/api/v1/me").json()
    assert me["memberships"][0]["organization_status"] == "pending"
    # No record tools until approval: the pending registrant is still a consumer in the UI.
    assert me["effective_role"] == "consumer"


def test_pending_organization_cannot_add_records(client: TestClient, applicant: User) -> None:
    org_id = client.post(ORGS, json=registration(), headers=csrf(client)).json()["id"]
    response = client.post(f"{ORGS}/{org_id}/records", json=record_body(), headers=csrf(client))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "organization_not_approved"


def test_registration_validates_input(client: TestClient, applicant: User) -> None:
    for bad in (
        {"emirate": "Texas"},
        {"emirate": None},
        {"name": " "},
        {"kind": "garage"},
        {"registration_number": "%%"},
        {"registration_number": "x" * 65},
    ):
        response = client.post(ORGS, json=registration(**bad), headers=csrf(client))
        assert response.status_code == 422, bad
        assert response.json()["error"]["code"] == "validation_error"


def test_licence_number_is_unique_ignoring_case(client: TestClient, db: Session, applicant: User) -> None:
    make_org(db, name="Existing Garage").registration_number = "DXB-778899"
    db.flush()
    response = client.post(ORGS, json=registration(registration_number="dxb-778899"), headers=csrf(client))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "registration_number_taken"


def test_one_pending_registration_at_a_time(client: TestClient, applicant: User) -> None:
    assert client.post(ORGS, json=registration(), headers=csrf(client)).status_code == 201
    second = client.post(ORGS, json=registration(registration_number="SHJ-1"), headers=csrf(client))
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "registration_pending"


def test_registration_needs_sign_in_csrf_and_a_non_admin(client: TestClient, db: Session) -> None:
    assert client.post(ORGS, json=registration(), headers=csrf(client)).status_code == 401
    add_user(db, "admin@example.ae", role=UserRole.PLATFORM_ADMIN)
    login(client, "admin@example.ae")
    assert client.post(ORGS, json=registration()).status_code == 403  # no CSRF header
    response = client.post(ORGS, json=registration(), headers=csrf(client))
    assert response.status_code == 403 and response.json()["error"]["code"] == "forbidden"


# --- reading and editing your own organization -----------------------------------------------------


def test_members_read_their_organization_others_cannot(app: FastAPI, client: TestClient, db: Session) -> None:
    mine, theirs = make_org(db, name="Mine"), make_org(db, name="Theirs")
    staff = add_user(db, "staff@example.ae")
    add_member(db, mine, staff, MemberRole.ENTITY_STAFF)
    login(client, staff.email)

    assert client.get(f"{ORGS}/{mine.id}").json()["name"] == "Mine"
    assert client.get(f"{ORGS}/{theirs.id}").status_code == 403
    assert client.get(f"{ORGS}/{uuid.uuid4()}").status_code == 404
    with other_client(app) as outsider:
        add_user(db, "outsider@example.ae")
        login(outsider, "outsider@example.ae")
        assert outsider.get(f"{ORGS}/{mine.id}").status_code == 403


def test_entity_admin_edits_details_staff_cannot(app: FastAPI, client: TestClient, db: Session) -> None:
    org = make_org(db, name="Old Name")
    boss, staff = add_user(db, "boss@example.ae"), add_user(db, "tech@example.ae")
    add_member(db, org, boss, MemberRole.ENTITY_ADMIN)
    add_member(db, org, staff, MemberRole.ENTITY_STAFF)
    login(client, boss.email)

    response = client.patch(f"{ORGS}/{org.id}", json={"name": "Falcon Bay Tyres", "emirate": "Sharjah"}, headers=csrf(client))

    assert response.status_code == 200
    assert (response.json()["name"], response.json()["emirate"]) == ("Falcon Bay Tyres", "Sharjah")
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "organization.updated"))
    assert event.details["changes"]["name"] == ["Old Name", "Falcon Bay Tyres"]
    with other_client(app) as staff_client:
        login(staff_client, staff.email)
        assert staff_client.patch(f"{ORGS}/{org.id}", json={"name": "Nope"}, headers=csrf(staff_client)).status_code == 403


def test_licence_number_is_locked_once_approved(client: TestClient, applicant: User, admin_client: TestClient) -> None:
    org_id = client.post(ORGS, json=registration(), headers=csrf(client)).json()["id"]
    assert client.patch(f"{ORGS}/{org_id}", json={"registration_number": "DXB-1"}, headers=csrf(client)).status_code == 200

    admin_client.post(f"{ADMIN_ORGS}/{org_id}/approve", headers=csrf(admin_client))

    response = client.patch(f"{ORGS}/{org_id}", json={"registration_number": "DXB-2"}, headers=csrf(client))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "registration_locked"
    assert client.patch(f"{ORGS}/{org_id}", json={"name": "Renamed Centre"}, headers=csrf(client)).status_code == 200


def test_rejected_registration_is_fixed_and_resubmitted(client: TestClient, applicant: User, admin_client: TestClient) -> None:
    org_id = client.post(ORGS, json=registration(), headers=csrf(client)).json()["id"]
    admin_client.post(f"{ADMIN_ORGS}/{org_id}/reject", json={"reason": "Licence number does not match the document."},
                      headers=csrf(admin_client))

    seen = client.get(f"{ORGS}/{org_id}").json()
    assert seen["status"] == "rejected"
    assert seen["rejection_reason"] == "Licence number does not match the document."

    client.patch(f"{ORGS}/{org_id}", json={"registration_number": "DXB-778900"}, headers=csrf(client))
    resubmitted = client.post(f"{ORGS}/{org_id}/resubmit", headers=csrf(client))

    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "pending" and resubmitted.json()["rejection_reason"] is None
    again = client.post(f"{ORGS}/{org_id}/resubmit", headers=csrf(client))
    assert again.status_code == 409 and again.json()["error"]["code"] == "not_rejected"


# --- platform admin: review ------------------------------------------------------------------------


def test_only_platform_admins_reach_the_admin_api(client: TestClient, db: Session) -> None:
    org = make_org(db)
    boss = add_user(db, "boss@example.ae")
    add_member(db, org, boss, MemberRole.ENTITY_ADMIN)
    login(client, boss.email)
    for response in (
        client.get(ADMIN_ORGS),
        client.get(f"{ADMIN_ORGS}/{org.id}"),
        client.post(ADMIN_ORGS, json=registration(), headers=csrf(client)),
        client.patch(f"{ADMIN_ORGS}/{org.id}", json={"name": "X Y"}, headers=csrf(client)),
        client.post(f"{ADMIN_ORGS}/{org.id}/approve", headers=csrf(client)),
        client.post(f"{ADMIN_ORGS}/{org.id}/reject", json={"reason": "Not allowed"}, headers=csrf(client)),
        client.delete(f"{ADMIN_ORGS}/{org.id}", headers=csrf(client)),
    ):
        assert response.status_code == 403
    assert db.get(Organization, org.id) is not None


def test_approval_lets_members_add_records(
    client: TestClient, db: Session, applicant: User, admin_client: TestClient, published: list
) -> None:
    org_id = client.post(ORGS, json=registration(), headers=csrf(client)).json()["id"]

    response = admin_client.post(f"{ADMIN_ORGS}/{org_id}/approve", headers=csrf(admin_client))

    assert response.status_code == 200
    assert response.json()["status"] == "approved" and response.json()["approved_at"] is not None
    assert ("organization.reviewed", {"organization_id": org_id, "name": "Corniche Tyre Centre",
                                      "status": "approved", "rejection_reason": None}) in published
    assert client.get("/api/v1/me").json()["effective_role"] == "entity_admin"
    assert client.post(f"{ORGS}/{org_id}/records", json=record_body(), headers=csrf(client)).status_code == 201
    again = admin_client.post(f"{ADMIN_ORGS}/{org_id}/approve", headers=csrf(admin_client))
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_approved"


def test_rejection_needs_a_reason_and_withdraws_approval(
    app: FastAPI, db: Session, admin_client: TestClient, published: list
) -> None:
    org = make_org(db)
    staff = add_user(db, "staff@example.ae")
    add_member(db, org, staff, MemberRole.ENTITY_STAFF)

    assert admin_client.post(f"{ADMIN_ORGS}/{org.id}/reject", json={"reason": "no"}, headers=csrf(admin_client)).status_code == 422
    response = admin_client.post(
        f"{ADMIN_ORGS}/{org.id}/reject", json={"reason": "Trade licence has expired."}, headers=csrf(admin_client)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected" and response.json()["approved_at"] is None
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "organization.rejected"))
    assert event.details["reason"] == "Trade licence has expired."
    assert published[-1][1]["status"] == "rejected"
    with other_client(app) as staff_client:
        login(staff_client, staff.email)
        blocked = staff_client.post(f"{ORGS}/{org.id}/records", json=record_body(), headers=csrf(staff_client))
        assert blocked.json()["error"]["code"] == "organization_not_approved"
    again = admin_client.post(f"{ADMIN_ORGS}/{org.id}/reject", json={"reason": "Still expired."}, headers=csrf(admin_client))
    assert again.status_code == 409


# --- platform admin: list, create, edit ------------------------------------------------------------


def test_list_puts_pending_first_and_filters(db: Session, admin_client: TestClient) -> None:
    approved = make_org(db, name="Approved Motors")
    pending = make_org(db, name="Pending Garage", status=OrganizationStatus.PENDING)
    make_org(db, name="Rejected Garage", status=OrganizationStatus.REJECTED)
    add_member(db, approved, add_user(db, "a@example.ae"), MemberRole.ENTITY_STAFF)
    make_record(db, make_vehicle(db), approved, add_user(db, "b@example.ae"))

    def names(**params) -> list[str]:
        return [item["name"] for item in admin_client.get(ADMIN_ORGS, params={"page_size": 100, **params}).json()["items"]]

    assert names()[0] == "Pending Garage"
    assert names(status="rejected") == ["Rejected Garage"]
    assert names(q="motors") == ["Approved Motors"]
    assert names(q=pending.registration_number.lower()) == ["Pending Garage"]
    assert names(emirate="Fujairah") == []
    assert admin_client.get(ADMIN_ORGS, params={"emirate": "Texas"}).status_code == 422
    row = next(i for i in admin_client.get(ADMIN_ORGS, params={"q": "Approved"}).json()["items"])
    assert (row["member_count"], row["record_count"]) == (1, 1)


def test_detail_lists_members(db: Session, admin_client: TestClient) -> None:
    org = make_org(db)
    add_member(db, org, add_user(db, "boss@example.ae", full_name="Hamad Boss"), MemberRole.ENTITY_ADMIN)
    detail = admin_client.get(f"{ADMIN_ORGS}/{org.id}").json()
    assert [(m["full_name"], m["role"]) for m in detail["members"]] == [("Hamad Boss", "entity_admin")]
    assert "password_hash" not in str(detail)


def test_admin_creates_an_approved_organization_and_edits_it(db: Session, admin_client: TestClient) -> None:
    created = admin_client.post(ADMIN_ORGS, json=registration(kind="dealership"), headers=csrf(admin_client))

    assert created.status_code == 201
    body = created.json()
    assert (body["status"], body["kind"], body["members"]) == ("approved", "dealership", [])
    assert admin_client.post(ADMIN_ORGS, json=registration(), headers=csrf(admin_client)).status_code == 409

    edited = admin_client.patch(f"{ADMIN_ORGS}/{body['id']}", json={"registration_number": "auh-1"}, headers=csrf(admin_client))
    assert edited.status_code == 200 and edited.json()["registration_number"] == "AUH-1"  # admins may change it
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "organization.created")) is not None


# --- platform admin: delete ------------------------------------------------------------------------


def test_delete_really_removes_the_organization_but_keeps_history(db: Session, admin_client: TestClient) -> None:
    org = make_org(db, name="Closing Garage")
    staff = add_user(db, "leaver@example.ae")
    membership = add_member(db, org, staff, MemberRole.ENTITY_STAFF)
    record = make_record(db, make_vehicle(db, VIN), org, staff)
    org_id, membership_id, record_id, staff_id = org.id, membership.id, record.id, staff.id

    response = admin_client.delete(f"{ADMIN_ORGS}/{org_id}", headers=csrf(admin_client))

    assert response.status_code == 204
    db.expunge_all()
    assert db.get(Organization, org_id) is None
    assert db.get(OrganizationMember, membership_id) is None
    assert db.get(User, staff_id) is not None  # the person keeps their account
    kept = db.get(ServiceRecord, record_id)
    assert kept.organization_id is None and kept.organization_name == "Closing Garage"
    timeline = admin_client.get(f"/api/v1/vehicles/{VIN}/timeline").json()
    assert timeline["records"][0]["organization_name"] == "Closing Garage"
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "organization.deleted"))
    assert event.details["name"] == "Closing Garage" and event.details["active_members"] == 1
    assert admin_client.get(f"{ADMIN_ORGS}/{org_id}").status_code == 404


def test_delete_requires_csrf(db: Session, admin_client: TestClient) -> None:
    org = make_org(db)
    assert admin_client.delete(f"{ADMIN_ORGS}/{org.id}").status_code == 403
    assert db.get(Organization, org.id) is not None
