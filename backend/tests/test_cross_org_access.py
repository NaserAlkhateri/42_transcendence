"""NA-06: no organization-scoped route lets one organization act on another. The caller is the entity admin
of a different, approved organization: the strongest outsider short of a platform admin."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, MemberRole, Organization, OrganizationMember, ServiceRecord, User
from tests.auth_helpers import add_member, add_user, csrf, login
from tests.factories import make_org, make_record, make_vehicle

VIN = "JTMHX01J5M4012345"
RECORD = {"vin": VIN, "service_date": "2026-01-10", "category": "maintenance", "work_codes": ["OIL_CHANGE"], "odometer_km": 50_000}
CORRECTION = {**{k: v for k, v in RECORD.items() if k != "vin"}, "correction_reason": "odometer"}


@pytest.fixture
def world(client: TestClient, db: Session) -> dict:
    """Falcon (the target) with an admin, a staff member and a record; Oasis whose admin signs in on `client`."""
    falcon, oasis = make_org(db, name="Falcon Bay Auto Care"), make_org(db, name="Oasis Line Motors")
    falcon_admin, falcon_staff = add_user(db, "falcon.admin@example.ae"), add_user(db, "falcon.staff@example.ae")
    add_member(db, falcon, falcon_admin, MemberRole.ENTITY_ADMIN)
    staff_membership = add_member(db, falcon, falcon_staff, MemberRole.ENTITY_STAFF)
    oasis_admin = add_user(db, "oasis.admin@example.ae")
    add_member(db, oasis, oasis_admin, MemberRole.ENTITY_ADMIN)
    record = make_record(db, make_vehicle(db, VIN), falcon, falcon_staff, notes="Falcon's private note")
    add_user(db, "someone@example.ae")
    login(client, oasis_admin.email)
    return {"falcon": falcon, "oasis": oasis, "membership": staff_membership, "record": record}


def requests(w: dict) -> list[tuple[str, str, dict | None]]:
    f = f"/api/v1/organizations/{w['falcon'].id}"
    m = w["membership"].id
    return [
        ("GET", f, None),
        ("PATCH", f, {"name": "Taken Over Garage"}),
        ("POST", f"{f}/resubmit", None),
        ("GET", f"{f}/members", None),
        ("POST", f"{f}/members", {"email": "someone@example.ae", "role": "entity_admin"}),
        ("POST", f"{f}/members/staff-accounts", {"email": "mole@example.ae", "full_name": "Mole", "role": "entity_admin"}),
        ("PATCH", f"{f}/members/{m}", {"role": "entity_admin"}),
        ("DELETE", f"{f}/members/{m}", None),
        ("POST", f"{f}/records", RECORD),
        ("GET", f"{f}/records?vin={VIN}", None),
        ("POST", f"{f}/records/{w['record'].id}/corrections", CORRECTION),
    ]


def test_another_organizations_admin_is_refused_everywhere(client: TestClient, db: Session, world: dict) -> None:
    before = {
        "records": db.scalar(select(func.count()).select_from(ServiceRecord)),
        "members": db.scalar(select(func.count()).select_from(OrganizationMember)),
        "users": db.scalar(select(func.count()).select_from(User)),
        "audit": db.scalar(select(func.count()).select_from(AuditEvent)),
    }
    for method, path, body in requests(world):
        response = client.request(method, path, json=body, headers=csrf(client))
        assert response.status_code == 403, f"{method} {path} -> {response.status_code}"
        assert response.json()["error"]["code"] == "forbidden", f"{method} {path}"
        assert "private note" not in response.text

    db.expire_all()
    assert db.get(Organization, world["falcon"].id).name == "Falcon Bay Auto Care"
    assert db.get(OrganizationMember, world["membership"].id).role == MemberRole.ENTITY_STAFF
    assert {
        "records": db.scalar(select(func.count()).select_from(ServiceRecord)),
        "members": db.scalar(select(func.count()).select_from(OrganizationMember)),
        "users": db.scalar(select(func.count()).select_from(User)),
        "audit": db.scalar(select(func.count()).select_from(AuditEvent)),
    } == before


def test_own_organization_id_with_another_organizations_objects(client: TestClient, world: dict) -> None:
    """Swapping only the inner id (a Falcon membership or record under Oasis's own URL) doesn't work either."""
    o = f"/api/v1/organizations/{world['oasis'].id}"
    assert client.patch(f"{o}/members/{world['membership'].id}", json={"role": "entity_admin"}, headers=csrf(client)).status_code == 404
    assert client.delete(f"{o}/members/{world['membership'].id}", headers=csrf(client)).status_code == 404
    correction = client.post(f"{o}/records/{world['record'].id}/corrections", json=CORRECTION, headers=csrf(client))
    assert correction.status_code == 403 and correction.json()["error"]["code"] == "not_your_record"
    listed = client.get(f"{o}/records?vin={VIN}")
    assert listed.status_code == 200 and listed.json() == []  # Oasis sees none of Falcon's records


def test_platform_routes_are_closed_to_entity_admins(client: TestClient, world: dict) -> None:
    for method, path in [
        ("GET", "/api/v1/admin/users"), ("GET", "/api/v1/admin/organizations"), ("GET", "/api/v1/admin/api-keys"),
        ("POST", f"/api/v1/admin/organizations/{world['falcon'].id}/reject"),
        ("DELETE", f"/api/v1/admin/organizations/{world['falcon'].id}"),
    ]:
        body = {"reason": "Hostile takeover attempt."} if path.endswith("/reject") else None
        assert client.request(method, path, json=body, headers=csrf(client)).status_code == 403, f"{method} {path}"
