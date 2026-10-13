import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.auth.dependencies import CurrentUser
from app.auth.permissions import require_org_role
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import MemberRole, Organization, OrganizationStatus, ServiceRecord, User, Vehicle
from app.schemas.records import CorrectionSubmission, OrgRecordOut, RecordSubmission, WorkCodeOut
from app.schemas.vehicle import TimelineRecord
from app.services import events
from app.services.records import AlreadyCorrectedError, submit_correction, submit_record
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


def to_org_record_out(record: ServiceRecord, vin: str, corrected_by_id: uuid.UUID | None = None) -> OrgRecordOut:
    return OrgRecordOut(
        **TimelineRecord.model_validate(record).model_dump(), vin=vin, staff_name=record.staff_name, notes=record.notes,
        corrected_by_id=corrected_by_id,
    )


def canonical_vin(raw: str) -> str:
    try:
        return normalize_vin(raw)
    except InvalidVinError as exc:
        raise ApiError(422, "invalid_vin", str(exc)) from exc


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
    vin = canonical_vin(body.vin)
    record = submit_record(db, organization=organization, staff=user, vin=vin, fields=body)
    db.commit()
    events.publish("record.added", record_added_payload(record, vin))
    return to_org_record_out(record, vin)


@router.post(
    "/organizations/{organization_id}/records/{record_id}/corrections",
    response_model=OrgRecordOut,
    status_code=status.HTTP_201_CREATED,
)
def create_correction(
    organization_id: uuid.UUID, record_id: uuid.UUID, body: CorrectionSubmission, user: CurrentUser, db: DbSession
) -> OrgRecordOut:
    """Append a correction of one of the organization's own records. The original stays unchanged and both
    are shown together. A record is corrected once; to fix a correction, correct the correction."""
    organization = submitting_organization(db, user, organization_id)
    original = db.get(ServiceRecord, record_id)
    if original is None:
        raise ApiError(404, "record_not_found", "Record not found.")
    if original.organization_id != organization.id:
        raise ApiError(403, "not_your_record", "Only the organization that created a record can correct it.")
    try:
        correction = submit_correction(
            db, organization=organization, staff=user, original=original, fields=body, reason=body.correction_reason
        )
    except AlreadyCorrectedError as exc:
        raise ApiError(409, "already_corrected", "This record already has a correction. Correct that one instead.") from exc
    vin = db.scalar(select(Vehicle.vin).where(Vehicle.id == correction.vehicle_id))
    db.commit()
    events.publish("record.added", record_added_payload(correction, vin))
    return to_org_record_out(correction, vin)


@router.get("/organizations/{organization_id}/records", response_model=list[OrgRecordOut])
def list_organization_records(
    organization_id: uuid.UUID, user: CurrentUser, db: DbSession, vin: Annotated[str, Query(max_length=40)]
) -> list[OrgRecordOut]:
    """The organization's own records for one VIN, newest first, with notes and whether each is corrected."""
    if db.get(Organization, organization_id) is None:
        raise ApiError(404, "organization_not_found", "Organization not found.")
    require_org_role(db, user, organization_id, SUBMITTER_ROLES)
    canonical = canonical_vin(vin)
    correction = aliased(ServiceRecord)
    rows = db.execute(
        select(ServiceRecord, correction.id)
        .join(Vehicle, Vehicle.id == ServiceRecord.vehicle_id)
        .outerjoin(correction, correction.corrects_record_id == ServiceRecord.id)
        .where(Vehicle.vin == canonical, ServiceRecord.organization_id == organization_id)
        .order_by(ServiceRecord.service_date.desc(), ServiceRecord.created_at.desc(), ServiceRecord.id)
    ).all()
    return [to_org_record_out(record, canonical, corrected_by_id) for record, corrected_by_id in rows]

