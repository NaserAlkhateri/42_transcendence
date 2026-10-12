"""Organization-scope guard used by organization, member and record routes (NA-03, NA-04, AG-03)."""

import uuid
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.auth.permissions import require_org_role
from app.db.session import get_db
from app.models import MemberRole, MemberStatus, UserRole
from tests.auth_helpers import add_member, add_user, login
from tests.factories import make_org

ADMINS_ONLY = {MemberRole.ENTITY_ADMIN}
ANY_MEMBER = {MemberRole.ENTITY_ADMIN, MemberRole.ENTITY_STAFF}


@pytest.fixture
def scoped_client(app: FastAPI) -> TestClient:
    @app.get("/test/orgs/{org_id}/admin-action")
    def admin_action(org_id: uuid.UUID, user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> dict:
        require_org_role(db, user, org_id, ADMINS_ONLY)
        return {"ok": True}

    @app.get("/test/orgs/{org_id}/member-action")
    def member_action(org_id: uuid.UUID, user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> dict:
        require_org_role(db, user, org_id, ANY_MEMBER)
        return {"ok": True}

    return TestClient(app, base_url="https://testserver")


def test_entity_roles_are_scoped_to_their_own_organization(scoped_client: TestClient, db: Session) -> None:
    mine, theirs = make_org(db, name="Mine"), make_org(db, name="Theirs")
    staff = add_user(db, "staff@example.ae")
    add_member(db, mine, staff, MemberRole.ENTITY_STAFF)
    login(scoped_client, staff.email)

    assert scoped_client.get(f"/test/orgs/{mine.id}/member-action").status_code == 200
    assert scoped_client.get(f"/test/orgs/{mine.id}/admin-action").status_code == 403  # staff, not admin
    assert scoped_client.get(f"/test/orgs/{theirs.id}/member-action").status_code == 403  # other organization


def test_entity_admin_is_admin_only_in_their_organization(scoped_client: TestClient, db: Session) -> None:
    mine, theirs = make_org(db, name="Mine"), make_org(db, name="Theirs")
    boss = add_user(db, "boss@example.ae")
    add_member(db, mine, boss, MemberRole.ENTITY_ADMIN)
    login(scoped_client, boss.email)

    assert scoped_client.get(f"/test/orgs/{mine.id}/admin-action").status_code == 200
    assert scoped_client.get(f"/test/orgs/{theirs.id}/admin-action").status_code == 403


def test_inactive_membership_grants_nothing(scoped_client: TestClient, db: Session) -> None:
    org = make_org(db)
    user = add_user(db, "former@example.ae")
    membership = add_member(db, org, user, MemberRole.ENTITY_ADMIN)
    membership.status = MemberStatus.INACTIVE
    db.flush()
    login(scoped_client, user.email)
    assert scoped_client.get(f"/test/orgs/{org.id}/member-action").status_code == 403


def test_consumer_and_platform_admin(scoped_client: TestClient, db: Session) -> None:
    org = make_org(db)
    add_user(db, "consumer@example.ae")
    add_user(db, "admin@example.ae", role=UserRole.PLATFORM_ADMIN)

    login(scoped_client, "consumer@example.ae")
    assert scoped_client.get(f"/test/orgs/{org.id}/member-action").status_code == 403
    login(scoped_client, "admin@example.ae")
    assert scoped_client.get(f"/test/orgs/{org.id}/admin-action").status_code == 200
