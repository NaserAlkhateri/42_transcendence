"""Fictional demo data for local runs and evaluation: `python -m app.seed`.

Safe to run on every start: it only inserts what is missing, and it adds service records only to a
vehicle that has none, because history is append-only. Every organization, person and VIN is invented.
"""

import sys
from datetime import UTC, date, datetime
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.core.config import get_settings
from app.db.session import get_engine
from app.models import (
    MemberRole,
    Organization,
    OrganizationKind,
    OrganizationMember,
    OrganizationStatus,
    RecordCategory,
    ServiceRecord,
    User,
    UserRole,
    Vehicle,
)

DEMO_DOMAIN = "sijil.demo"  # .demo is not a real top-level domain, so no real inbox exists


class OrgSpec(NamedTuple):
    registration_number: str
    name: str
    kind: OrganizationKind
    status: OrganizationStatus
    emirate: str


class UserSpec(NamedTuple):
    local_part: str
    full_name: str
    role: UserRole
    organization: str | None = None  # registration number
    member_role: MemberRole | None = None


class RecordSpec(NamedTuple):
    organization: str  # registration number
    staff: str  # user local part
    category: RecordCategory
    work_codes: list[str]
    odometer_km: int
    service_date: date
    flagged: bool = False
    corrects: int | None = None  # index of the earlier record (same vehicle) this one corrects


class VehicleSpec(NamedTuple):
    vin: str
    make: str
    model: str
    model_year: int
    records: list[RecordSpec]


ORGANIZATIONS = [
    OrgSpec("DEMO-WS-001", "Falcon Bay Auto Care", OrganizationKind.WORKSHOP, OrganizationStatus.APPROVED, "Dubai"),
    OrgSpec("DEMO-DL-002", "Oasis Line Motors", OrganizationKind.DEALERSHIP, OrganizationStatus.APPROVED, "Abu Dhabi"),
    OrgSpec("DEMO-WS-003", "Sand Dune Garage", OrganizationKind.WORKSHOP, OrganizationStatus.PENDING, "Sharjah"),
]

# Fictional people with names typical of the UAE's mixed workforce. Display names only; emails stay role-based.
USERS = [
    UserSpec("admin", "Platform Admin", UserRole.PLATFORM_ADMIN),
    UserSpec("consumer", "Mariam Al Hashimi", UserRole.CONSUMER),
    UserSpec("falcon.admin", "Khalid Al Mansoori", UserRole.CONSUMER, "DEMO-WS-001", MemberRole.ENTITY_ADMIN),
    UserSpec("falcon.staff", "Arjun Nair", UserRole.CONSUMER, "DEMO-WS-001", MemberRole.ENTITY_STAFF),
    UserSpec("oasis.admin", "Fatima Al Zaabi", UserRole.CONSUMER, "DEMO-DL-002", MemberRole.ENTITY_ADMIN),
    UserSpec("oasis.staff", "Joseph Santos", UserRole.CONSUMER, "DEMO-DL-002", MemberRole.ENTITY_STAFF),
    UserSpec("sanddune.admin", "Omar Haddad", UserRole.CONSUMER, "DEMO-WS-003", MemberRole.ENTITY_ADMIN),
]

# Among the most common cars on UAE roads, with GCC-market VIN prefixes (JTM/JTN Toyota Japan, JN8 Nissan Japan).
# Work codes follow the local climate: A/C, batteries and tyres wear fast in the heat, air filters in the dust.
# MDHBN7AD0P0012345 (2023 Nissan Sunny) is deliberately not seeded: it is the demo VIN for the "Watch" flow.
VEHICLES = [
    VehicleSpec("JTMHX01J5M4012345", "Toyota", "Land Cruiser", 2021, [  # clean history
        RecordSpec("DEMO-WS-001", "falcon.staff", RecordCategory.MAINTENANCE, ["OIL_CHANGE", "AIR_FILTER"], 18_400, date(2024, 3, 12)),
        RecordSpec("DEMO-WS-001", "falcon.staff", RecordCategory.MAINTENANCE, ["AC_SERVICE", "BATTERY_REPLACE"], 41_200, date(2024, 12, 2)),
        RecordSpec("DEMO-DL-002", "oasis.staff", RecordCategory.REPAIR, ["TYRE_REPLACE"], 63_900, date(2025, 9, 18)),
    ]),
    VehicleSpec("JN8AY2NY4K9012345", "Nissan", "Patrol", 2019, [  # mileage went down: accepted and flagged
        RecordSpec("DEMO-DL-002", "oasis.staff", RecordCategory.MAINTENANCE, ["OIL_CHANGE"], 96_000, date(2024, 6, 3)),
        RecordSpec("DEMO-WS-001", "falcon.staff", RecordCategory.REPAIR, ["AC_SERVICE"], 121_500, date(2025, 7, 21)),
        RecordSpec("DEMO-WS-001", "falcon.staff", RecordCategory.MAINTENANCE, ["OIL_CHANGE"], 88_300, date(2026, 4, 11), flagged=True),
    ]),
    VehicleSpec("JTNBK3EK6N3012345", "Toyota", "Camry", 2022, [  # mistyped reading, then a linked correction
        RecordSpec("DEMO-WS-001", "falcon.staff", RecordCategory.MAINTENANCE, ["OIL_CHANGE"], 54_000, date(2025, 11, 5)),
        # The correction replaces the original reading, so there is no earlier effective reading to compare: not flagged.
        RecordSpec("DEMO-WS-001", "falcon.staff", RecordCategory.MAINTENANCE, ["OIL_CHANGE"], 45_100, date(2025, 11, 5), corrects=0),
    ]),
]


def seed(db: Session, demo_password: str) -> None:
    """Insert any missing demo rows into the current transaction (the caller commits)."""
    password_hash = hash_password(demo_password)
    orgs = {spec.registration_number: _get_or_create_org(db, spec) for spec in ORGANIZATIONS}
    users: dict[str, User] = {}
    for spec in USERS:
        users[spec.local_part] = _get_or_create_user(db, spec, password_hash)
        if spec.organization is not None and spec.member_role is not None:
            _ensure_membership(db, orgs[spec.organization], users[spec.local_part], spec.member_role)
    for spec in VEHICLES:
        vehicle = _get_or_create_vehicle(db, spec)
        has_history = db.scalar(select(ServiceRecord.id).where(ServiceRecord.vehicle_id == vehicle.id).limit(1))
        if has_history is None:
            _add_records(db, vehicle, spec.records, orgs, users)
    db.flush()


def _get_or_create_org(db: Session, spec: OrgSpec) -> Organization:
    org = db.scalar(select(Organization).where(Organization.registration_number == spec.registration_number))
    if org is None:
        org = Organization(
            registration_number=spec.registration_number,
            name=spec.name,
            kind=spec.kind,
            status=spec.status,
            emirate=spec.emirate,
            approved_at=datetime.now(UTC) if spec.status is OrganizationStatus.APPROVED else None,
        )
        db.add(org)
        db.flush()
    return org


def _get_or_create_user(db: Session, spec: UserSpec, password_hash: str) -> User:
    email = f"{spec.local_part}@{DEMO_DOMAIN}"
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, password_hash=password_hash, full_name=spec.full_name, role=spec.role)
        db.add(user)
        db.flush()
    return user


def _ensure_membership(db: Session, org: Organization, user: User, role: MemberRole) -> None:
    exists = db.scalar(
        select(OrganizationMember.id).where(
            OrganizationMember.organization_id == org.id, OrganizationMember.user_id == user.id
        )
    )
    if exists is None:
        db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=role))
        db.flush()


def _get_or_create_vehicle(db: Session, spec: VehicleSpec) -> Vehicle:
    vehicle = db.scalar(select(Vehicle).where(Vehicle.vin == spec.vin))
    if vehicle is None:
        vehicle = Vehicle(vin=spec.vin, make=spec.make, model=spec.model, model_year=spec.model_year)
        db.add(vehicle)
        db.flush()
    return vehicle


def _add_records(
    db: Session, vehicle: Vehicle, specs: list[RecordSpec], orgs: dict[str, Organization], users: dict[str, User]
) -> None:
    created: list[ServiceRecord] = []
    for spec in specs:
        org, staff = orgs[spec.organization], users[spec.staff]
        record = ServiceRecord(
            vehicle_id=vehicle.id,
            organization_id=org.id,
            staff_id=staff.id,
            organization_name=org.name,
            staff_name=staff.full_name,
            category=spec.category,
            work_codes=spec.work_codes,
            odometer_km=spec.odometer_km,
            service_date=spec.service_date,
            is_mileage_flagged=spec.flagged,
            corrects_record_id=created[spec.corrects].id if spec.corrects is not None else None,
        )
        db.add(record)
        db.flush()
        created.append(record)


def main() -> int:
    password = get_settings().seed_demo_password
    if not password:
        print("SEED_DEMO_PASSWORD is not set; refusing to create demo accounts without it.", file=sys.stderr)
        return 1
    with Session(get_engine()) as db, db.begin():
        seed(db, password)
    print("Demo data is in place.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
