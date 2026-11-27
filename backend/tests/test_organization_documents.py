import uuid
from io import BytesIO
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1 import documents
from app.core.document_limits import DOCUMENT_MAX_BYTES
from app.models import AuditEvent, MemberRole, OrganizationDocument, OrganizationStatus, UserRole
from app.services.document_storage import storage_unavailable
from tests.auth_helpers import add_member, add_user, csrf, login
from tests.factories import make_org


class MemoryStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.fail_remove = False

    def put(self, key: str, data: bytes, media_type: str) -> None:
        self.objects[key] = data

    def get(self, key: str, expected_size: int) -> bytes:
        data = self.objects[key]
        assert len(data) == expected_size
        return data

    def remove(self, key: str) -> None:
        if self.fail_remove:
            raise storage_unavailable()
        self.objects.pop(key, None)


def png() -> bytes:
    out = BytesIO()
    Image.new("RGB", (3, 3), "green").save(out, format="PNG")
    return out.getvalue()


def pdf(*, large: bool = False) -> bytes:
    out = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    if large:
        writer.add_metadata({"/Title": "x" * 1_100_000})
    writer.write(out)
    return out.getvalue()


@pytest.fixture
def document_setup(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch):
    organization = make_org(db, status=OrganizationStatus.PENDING)
    other = make_org(db)
    owner = add_user(db, "document.owner@example.ae")
    staff = add_user(db, "document.staff@example.ae")
    outsider = add_user(db, "document.outsider@example.ae")
    admin = add_user(db, "document.admin@example.ae", role=UserRole.PLATFORM_ADMIN)
    add_member(db, organization, owner, MemberRole.ENTITY_ADMIN)
    add_member(db, organization, staff, MemberRole.ENTITY_STAFF)
    add_member(db, other, outsider, MemberRole.ENTITY_ADMIN)
    store = MemoryStorage()
    monkeypatch.setattr(documents, "get_document_storage", lambda: store)
    assert login(client, owner.email).status_code == 200
    return organization, other, staff, outsider, admin, store


def upload(client: TestClient, path: str, filename: str, content_type: str, body: bytes):
    return client.post(path, content=body, headers={
        **csrf(client), "Content-Type": content_type, "X-File-Name": quote(filename),
    })


def test_licence_document_lifecycle(client: TestClient, db: Session, document_setup) -> None:
    org, other, staff, outsider, admin, store = document_setup
    path = f"/api/v1/organizations/{org.id}/documents"
    manage = f"/api/v1/admin/organizations/{org.id}"
    body = png()
    response = upload(client, path, "رخصة.png", "image/png", body)
    assert response.status_code == 201, response.text
    metadata = response.json()
    doc = db.get(OrganizationDocument, uuid.UUID(metadata["id"]))
    assert doc is not None and store.objects == {doc.object_key: body}
    assert {"object_key", "uploaded_by_id"}.isdisjoint(metadata)
    file_path = f"{path}/{doc.id}"
    admin_file_path = f"{manage}/documents/{doc.id}"
    download = client.get(file_path)
    assert download.content == body
    assert download.headers["content-disposition"].startswith("attachment; filename*=UTF-8''")
    assert download.headers["cache-control"] == "private, no-store"
    assert client.delete(admin_file_path, headers=csrf(client)).status_code == 403

    for user in (staff, outsider):
        client.cookies.clear()
        assert login(client, user.email).status_code == 200
        assert client.get(path).status_code == 403
        assert client.get(file_path).status_code == 403
        assert upload(client, path, "licence.png", "image/png", body).status_code == 403
    assert client.get(f"/api/v1/organizations/{other.id}/documents/{doc.id}").status_code == 404

    client.cookies.clear()
    assert login(client, admin.email).status_code == 200
    assert client.get(manage).json()["documents"] == [metadata]
    assert client.get(admin_file_path).content == body
    assert client.delete(manage, headers=csrf(client)).status_code == 409
    store.fail_remove = True
    assert client.delete(admin_file_path, headers=csrf(client)).status_code == 503
    assert client.get(admin_file_path).status_code == 404
    assert client.get(manage).json()["documents"][0]["removal_pending"] is True
    store.fail_remove = False
    removed = client.delete(admin_file_path, headers=csrf(client))
    assert removed.status_code == 200 and removed.json()["deleted_at"]
    assert removed.json()["removal_pending"] is False and not store.objects
    assert client.delete(admin_file_path, headers=csrf(client)).status_code == 200
    assert db.scalar(select(func.count()).select_from(AuditEvent).where(
        AuditEvent.action == "organization.document_removed",
    )) == 1
    assert client.delete(manage, headers=csrf(client)).status_code == 204


def test_upload_checks_type_format_size_and_csrf(client: TestClient, document_setup) -> None:
    org, _, _, _, _, _ = document_setup
    path = f"/api/v1/organizations/{org.id}/documents"
    assert client.post(path, content=png(), headers={"Content-Type": "image/png", "X-File-Name": "a.png"}).status_code == 403
    assert upload(client, path, "a.svg", "image/svg+xml", b"<svg/>").status_code == 415
    assert upload(client, path, "a.png", "image/png", b"\x89PNG\r\n\x1a\n").status_code == 422
    assert upload(client, path, "a.pdf", "application/pdf", png()).status_code == 422
    assert upload(client, path, "../a.pdf", "application/pdf", pdf()).status_code == 422
    assert upload(client, path, "a.pdf", "application/pdf", b"x" * (DOCUMENT_MAX_BYTES + 1)).status_code == 413
    # A valid PDF over the default 1 MB JSON limit uses the separate upload limit.
    assert upload(client, path, "licence.pdf", "application/pdf", pdf(large=True)).status_code == 201
    client.cookies.clear()
    assert client.get(path).status_code == 401
