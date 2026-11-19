import uuid

from pydantic import BaseModel

from app.schemas.records import OrgRecordOut


class RecordSearchItem(OrgRecordOut):
    """A search result: the record as its organization sees it (staff name, private notes, correction links)
    plus the vehicle facts. Only organization members and platform admins can search."""

    make: str | None
    model: str | None
    model_year: int | None
    organization_id: uuid.UUID | None  # None once the organization is deleted; organization_name keeps the name


class RecordSearchPage(BaseModel):
    items: list[RecordSearchItem]
    total: int  # every match, not just this page
    page: int
    page_size: int
