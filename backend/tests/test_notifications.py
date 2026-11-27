from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import MemberRole, Notification, OrganizationStatus, UserRole
from tests.auth_helpers import add_member, add_user, csrf, login
from tests.factories import make_org

PATH = "/api/v1/notifications"


def sign_in(client: TestClient, email: str) -> dict[str, str]:
    client.cookies.clear()
    assert login(client, email).status_code == 200
    return csrf(client)


def test_inbox_pagination_read_state_and_owner_isolation(client: TestClient, db: Session) -> None:
    owner = add_user(db, "inbox.owner@example.ae")
    other = add_user(db, "inbox.other@example.ae")
    now = datetime.now(UTC)
    notices = [Notification(user_id=owner.id, event_type="account.updated", payload={"secret": "private"},
                            created_at=now - timedelta(seconds=i)) for i in range(3)]
    foreign = Notification(user_id=other.id, event_type="account.updated", payload={})
    db.add_all([*notices, foreign])
    db.flush()
    assert client.get(PATH).status_code == 401
    headers = sign_in(client, owner.email)
    result = client.get(PATH, params={"page_size": 1, "page": 2}).json()
    [row] = result["items"]
    assert row["id"] == str(notices[1].id) and row["read_at"] is None
    assert "secret" not in row and "payload" not in row and "user_id" not in row
    assert result["total"] == result["unread_count"] == 3
    assert client.patch(f"{PATH}/{foreign.id}", json={"read": True}, headers=headers).status_code == 404
    target = f"{PATH}/{notices[1].id}"
    assert client.patch(target, json={"read": True}).status_code == 403
    first = client.patch(target, json={"read": True}, headers=headers).json()
    assert first["read_at"] is not None
    assert client.patch(target, json={"read": True}, headers=headers).json()["read_at"] == first["read_at"]
    assert client.get(PATH, params={"unread": "true"}).json()["total"] == 2
    assert client.patch(target, json={"read": False}, headers=headers).json()["read_at"] is None
    assert client.post(f"{PATH}/read-all", headers=headers).status_code == 204
    assert client.get(PATH, params={"unread": "true"}).json() == {"items": [], "total": 0, "unread_count": 0}
    sign_in(client, other.email)
    assert client.get(PATH).json()["unread_count"] == 1


def test_create_update_and_remove_membership_deliver_to_affected_account(client: TestClient, db: Session) -> None:
    org = make_org(db)
    owner = add_user(db, "inbox.manager@example.ae")
    member = add_user(db, "inbox.member@example.ae")
    add_member(db, org, owner, MemberRole.ENTITY_ADMIN)
    headers = sign_in(client, owner.email)
    base = f"/api/v1/organizations/{org.id}/members"
    created = client.post(base, json={"email": member.email, "role": "entity_staff"}, headers=headers)
    assert created.status_code == 201, created.text
    target = f"{base}/{created.json()['membership_id']}"
    assert client.patch(target, json={"status": "inactive"}, headers=headers).status_code == 200
    # A no-op must not produce another update notice.
    assert client.patch(target, json={"status": "inactive"}, headers=headers).status_code == 200
    assert client.delete(target, headers=headers).status_code == 204
    assert client.get(PATH).json()["total"] == 0
    sign_in(client, member.email)
    result = client.get(PATH).json()
    assert result["total"] == result["unread_count"] == 3
    assert {row["event_type"] for row in result["items"]} == {"membership.added", "membership.updated", "membership.removed"}
    assert all(row["organization_name"] == org.name for row in result["items"])


def test_organization_review_and_removal_keep_private_notices(client: TestClient, db: Session) -> None:
    org = make_org(db, status=OrganizationStatus.PENDING)
    account = add_user(db, "inbox.applicant@example.ae")
    admin = add_user(db, "inbox.platform@example.ae", role=UserRole.PLATFORM_ADMIN)
    add_member(db, org, account, MemberRole.ENTITY_ADMIN)
    headers = sign_in(client, admin.email)
    path = f"/api/v1/admin/organizations/{org.id}"
    assert client.post(f"{path}/reject", json={"reason": "Private review explanation"}, headers=headers).status_code == 200
    assert client.delete(path, headers=headers).status_code == 204
    sign_in(client, account.email)
    items = {item["event_type"]: item for item in client.get(PATH).json()["items"]}
    assert set(items) == {"organization.reviewed", "organization.deleted"}
    assert items["organization.reviewed"]["status"] == "rejected"
    assert "Private review explanation" not in str(items)
