from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import seed as seed_module
from app.auth.passwords import verify_password
from app.core.config import Settings
from app.models import Organization, OrganizationMember, OrganizationStatus, ServiceRecord, User, UserRole, Vehicle
from app.seed import seed

MODELS = (Organization, User, OrganizationMember, Vehicle, ServiceRecord)


def counts(db: Session) -> tuple[int, ...]:
    return tuple(db.scalar(select(func.count()).select_from(model)) for model in MODELS)


def test_seed_creates_the_demo_world(db: Session) -> None:
    seed(db, "demo-pass-123")
    assert counts(db) == (3, 7, 5, 3, 8)

    admin = db.scalar(select(User).where(User.email == "admin@sijil.demo"))
    assert admin.role is UserRole.PLATFORM_ADMIN
    assert verify_password(admin.password_hash, "demo-pass-123")
    assert not verify_password(admin.password_hash, "wrong")

    pending = db.scalars(select(Organization.name).where(Organization.status == OrganizationStatus.PENDING)).all()
    assert pending == ["Sand Dune Garage"]

    flagged = db.scalars(select(ServiceRecord).where(ServiceRecord.is_mileage_flagged)).all()
    assert [record.odometer_km for record in flagged] == [88_300]

    corrections = db.scalars(select(ServiceRecord).where(ServiceRecord.corrects_record_id.is_not(None))).all()
    assert len(corrections) == 1


def test_seed_is_idempotent(db: Session) -> None:
    seed(db, "demo-pass-123")
    first = counts(db)
    seed(db, "demo-pass-123")
    assert counts(db) == first


def test_seeded_flagged_vehicle_is_served_by_the_timeline(client: TestClient, db: Session) -> None:
    seed(db, "demo-pass-123")
    body = client.get("/api/v1/vehicles/JN8AY2NY4K9012345/timeline").json()
    assert body["vehicle"] == {"vin": "JN8AY2NY4K9012345", "make": "Nissan", "model": "Patrol", "model_year": 2019}
    assert [record["is_mileage_flagged"] for record in body["records"]] == [True, False, False]


def test_seeded_correction_points_at_the_mistyped_reading(client: TestClient, db: Session) -> None:
    seed(db, "demo-pass-123")
    records = client.get("/api/v1/vehicles/JTNBK3EK6N3012345/timeline").json()["records"]
    # Same date and, inside one test transaction, the same created_at: find the pair by its link, not its order.
    [correction] = [record for record in records if record["corrects_record_id"]]
    [original] = [record for record in records if record["id"] == correction["corrects_record_id"]]
    assert (correction["odometer_km"], original["odometer_km"]) == (45_100, 54_000)
    assert correction["corrects_record_id"] == original["id"]


def test_demo_vin_for_the_watch_flow_has_no_history(client: TestClient, db: Session) -> None:
    seed(db, "demo-pass-123")
    assert client.get("/api/v1/vehicles/MDHBN7AD0P0012345/timeline").json()["vehicle"] is None


def test_cli_refuses_to_run_without_demo_password(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        seed_module, "get_settings", lambda: Settings(database_url="postgresql+psycopg://unused", seed_demo_password=None)
    )
    assert seed_module.main() == 1
    assert "SEED_DEMO_PASSWORD" in capsys.readouterr().err
