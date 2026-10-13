import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CorrectionReason, MemberRole, OrganizationMember, ServiceRecord, User
from tests.factories import make_org, make_record, make_user, make_vehicle

EXPECTED_TABLES = {
    "users", "sessions", "organizations", "organization_members", "vehicles", "service_records",
    "attachments", "watchlists", "notifications", "api_keys", "partner_watchlists", "audit_events",
}


def test_migration_creates_every_table(engine: Engine) -> None:
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_models_match_migrations(alembic_cfg: Config) -> None:
    command.check(alembic_cfg)  # raises if autogenerate would emit any change


def test_migrations_downgrade_and_upgrade_cleanly(alembic_cfg: Config, engine: Engine) -> None:
    command.downgrade(alembic_cfg, "base")
    assert "service_records" not in inspect(engine).get_table_names()
    command.upgrade(alembic_cfg, "head")
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_vin_is_unique(db: Session) -> None:
    make_vehicle(db, "JTDBR32E720123456")
    with pytest.raises(IntegrityError):
        make_vehicle(db, "JTDBR32E720123456")
    db.rollback()


def test_database_rejects_non_canonical_vin(db: Session) -> None:
    with pytest.raises(IntegrityError):
        make_vehicle(db, "jtdbr32e720123456")
    db.rollback()


def test_database_rejects_upper_case_email(db: Session) -> None:
    db.add(User(email="Someone@Test.Sijil", password_hash="x", full_name="Someone"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_service_records_reject_update(db: Session) -> None:
    record = make_record(db, make_vehicle(db), make_org(db), make_user(db))
    with pytest.raises(IntegrityError, match="append-only"):
        db.execute(text("UPDATE service_records SET odometer_km = 1 WHERE id = :id"), {"id": record.id})
    db.rollback()


def test_service_records_reject_delete(db: Session) -> None:
    record = make_record(db, make_vehicle(db), make_org(db), make_user(db))
    with pytest.raises(IntegrityError, match="append-only"):
        db.execute(text("DELETE FROM service_records WHERE id = :id"), {"id": record.id})
    db.rollback()


def test_deleting_organization_keeps_history_with_name_snapshot(db: Session) -> None:
    org = make_org(db, name="Falcon Bay Auto Care")
    record = make_record(db, make_vehicle(db), org, make_user(db))
    db.delete(org)
    db.flush()
    org_id, org_name = db.execute(
        select(ServiceRecord.organization_id, ServiceRecord.organization_name).where(ServiceRecord.id == record.id)
    ).one()
    assert org_id is None
    assert org_name == "Falcon Bay Auto Care"


def test_deleting_user_keeps_history_and_cascades_memberships(db: Session) -> None:
    org = make_org(db)
    staff = make_user(db, full_name="Omar Technician")
    member = OrganizationMember(organization_id=org.id, user_id=staff.id, role=MemberRole.ENTITY_STAFF)
    db.add(member)
    record = make_record(db, make_vehicle(db), org, staff)
    member_id = member.id
    db.delete(staff)
    db.flush()
    staff_id, staff_name = db.execute(
        select(ServiceRecord.staff_id, ServiceRecord.staff_name).where(ServiceRecord.id == record.id)
    ).one()
    assert staff_id is None
    assert staff_name == "Omar Technician"
    assert db.scalar(select(func.count()).select_from(OrganizationMember).where(OrganizationMember.id == member_id)) == 0


def test_vehicle_with_history_cannot_be_deleted(db: Session) -> None:
    vehicle = make_vehicle(db)
    make_record(db, vehicle, make_org(db), make_user(db))
    with pytest.raises(IntegrityError):
        db.execute(text("DELETE FROM vehicles WHERE id = :id"), {"id": vehicle.id})
    db.rollback()


def test_a_record_can_be_corrected_only_once(db: Session) -> None:
    # Corrections form a chain: to fix a correction, correct the correction. Two corrections of one record
    # would leave two competing "effective" readings.
    org, staff, vehicle = make_org(db), make_user(db), make_vehicle(db)
    original = make_record(db, vehicle, org, staff)
    make_record(db, vehicle, org, staff, corrects=original, reason=CorrectionReason.ODOMETER)
    with pytest.raises(IntegrityError):
        make_record(db, vehicle, org, staff, corrects=original, reason=CorrectionReason.SERVICE_DATE)


def test_only_corrections_carry_a_reason_and_every_correction_has_one(db: Session) -> None:
    org, staff, vehicle = make_org(db), make_user(db), make_vehicle(db)
    original = make_record(db, vehicle, org, staff)
    with pytest.raises(IntegrityError), db.begin_nested():
        make_record(db, vehicle, org, staff, corrects=original, reason=None)
    with pytest.raises(IntegrityError), db.begin_nested():
        make_record(db, vehicle, org, staff, reason=CorrectionReason.OTHER)

