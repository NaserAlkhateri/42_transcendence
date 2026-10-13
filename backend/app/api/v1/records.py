import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.auth.permissions import require_org_role
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import MemberRole, Organization, OrganizationStatus, ServiceRecord, User
from app.schemas.records import OrgRecordOut, RecordSubmission, WorkCodeOut
from app.schemas.vehicle import TimelineRecord
from app.services import events
from app.services.records import submit_record
from app.services.vin import InvalidVinError, normalize_vin
from app.services.work_codes import WORK_CODES

router = APIRouter(tags=["records"])

DbSession = Annotated[Session, Depends(get_db)]
SUBMITTER_ROLES = {MemberRole.ENTITY_ADMIN, MemberRole.ENTITY_STAFF}


@router.get("/work-codes", response_model=list[WorkCodeOut])
def list_work_codes() -> list[WorkCodeOut]:
    """The predefined work codes, with English and Arabic labels."""
    return [WorkCodeOut(**work_code._asdict()) for work_code in WORK_CODES]


def submitting_organization(db: Session, user: User, organization_id: uuid.UUID) -> Organization:
    """The organization `user` may write history for: an active admin/staff membership of an approved
    organization. Platform admins cannot write history either."""
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise ApiError(404, "organization_not_found", "Organization not found.")
    require_org_role(db, user, organization_id, SUBMITTER_ROLES, allow_platform_admin=False)
    if organization.status != OrganizationStatus.APPROVED:
        raise ApiError(403, "organization_not_approved", "Your organization must be approved before it can add records.")
    return organization


def to_org_record_out(record: ServiceRecord, vin: str) -> OrgRecordOut:
    return OrgRecordOut(
        **TimelineRecord.model_validate(record).model_dump(), vin=vin, staff_name=record.staff_name, notes=record.notes
    )


def record_added_payload(record: ServiceRecord, vin: str) -> dict:
    """Consumer-safe: what a live timeline or a watchlist alert needs, never notes or staff."""
    return {
        "vin": vin,
        "record_id": str(record.id),
        "service_date": record.service_date.isoformat(),
        "is_mileage_flagged": record.is_mileage_flagged,
        "corrects_record_id": str(record.corrects_record_id) if record.corrects_record_id else None,
    }


@router.post("/organizations/{organization_id}/records", response_model=OrgRecordOut, status_code=status.HTTP_201_CREATED)
def create_record(organization_id: uuid.UUID, body: RecordSubmission, user: CurrentUser, db: DbSession) -> OrgRecordOut:
    """Append a service record. A reading that does not fit the vehicle's history is accepted and flagged."""
    organization = submitting_organization(db, user, organization_id)
    try:
        vin = normalize_vin(body.vin)
    except InvalidVinError as exc:
        raise ApiError(422, "invalid_vin", str(exc)) from exc
    record = submit_record(db, organization=organization, staff=user, vin=vin, fields=body)
    db.commit()
    events.publish("record.added", record_added_payload(record, vin))
    return to_org_record_out(record, vin)
