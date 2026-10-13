import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.models import CorrectionReason, RecordCategory, ServiceRecord, Vehicle
from tests.factories import make_org, make_record, make_user

VIN = "JN8AY2NY4K9012345"
URL = f"/api/v1/vehicles/{VIN}/report.pdf"


@pytest.fixture
def patrol(db: Session) -> dict[str, ServiceRecord]:
    """A 2019 Nissan Patrol: a normal service, a flagged lower reading, and a typo with its correction."""
    vehicle = Vehicle(vin=VIN, make="Nissan", model="Patrol", model_year=2019)
    db.add(vehicle)
    db.flush()
    falcon = make_org(db, name="Falcon Bay Auto Care")
    oasis = make_org(db, name="Oasis Line Motors")
    staff = make_user(db, full_name="Arjun Nair")
    records = {
        "ok": make_record(db, vehicle, oasis, staff, odometer_km=121_500, service_date=date(2025, 7, 21),
                          category=RecordCategory.REPAIR, notes="Customer phone 050 000 0000"),
        "flagged": make_record(db, vehicle, falcon, staff, odometer_km=88_300, service_date=date(2026, 4, 11), flagged=True),
        "typo": make_record(db, vehicle, falcon, staff, odometer_km=990_000, service_date=date(2026, 9, 20)),
    }
    records["fix"] = make_record(db, vehicle, falcon, staff, odometer_km=139_000, service_date=date(2026, 9, 20),
                                 corrects=records["typo"], reason=CorrectionReason.ODOMETER, notes="Extra zero typed")
    return records


def pdf_text(content: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(content)).pages)


def embedded_fonts(content: bytes) -> set[str]:
    fonts: set[str] = set()
    for page in PdfReader(io.BytesIO(content)).pages:
        for font in page["/Resources"]["/Font"].values():
            fonts.add(str(font.get_object()["/BaseFont"]))
    return fonts


def test_report_is_a_pdf_download_named_after_the_vin(client: TestClient, patrol) -> None:
    response = client.get(URL.replace(VIN, "jn8ay2ny4k9-012345"))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == f'attachment; filename="sijil-report-{VIN}.pdf"'
    assert response.content.startswith(b"%PDF")


def test_report_shows_the_vehicle_every_record_and_its_warnings(client: TestClient, patrol) -> None:
    text = pdf_text(client.get(URL).content)

    for expected in [VIN, "2019 Nissan Patrol", "Falcon Bay Auto Care", "Oasis Line Motors", "121,500 km", "88,300 km",
                     "Mileage warning", "Repair", "Oil change"]:
        assert expected in text, expected


def test_report_shows_a_correction_together_with_the_original_it_replaces(client: TestClient, patrol) -> None:
    text = pdf_text(client.get(URL).content)

    assert "Correction of the 20 Sep 2026 record" in text
    assert "Reason: Odometer reading" in text
    assert "990,000 km" in text  # the original stays in the report
    assert text.index("139,000 km") < text.index("990,000 km")  # the original follows its correction
    assert "Corrected by the record above" in text


def test_report_never_contains_staff_names_or_private_notes(client: TestClient, patrol) -> None:
    text = pdf_text(client.get(URL).content)
    for private in ["Arjun Nair", "Customer phone", "050 000 0000", "Extra zero typed"]:
        assert private not in text


def test_report_is_bilingual(client: TestClient, patrol) -> None:
    content = client.get(URL).content
    fonts = embedded_fonts(content)
    assert any("NotoSansArabic" in font for font in fonts)  # Arabic text is set in the bundled Arabic font
    assert any("NotoSans" in font and "Arabic" not in font for font in fonts)
    assert "Vehicle service report" in pdf_text(content)


def test_report_states_it_is_not_an_official_record(client: TestClient, patrol) -> None:
    assert "Not an official or government record" in pdf_text(client.get(URL).content)


def test_vin_without_history_has_no_report(client: TestClient) -> None:
    response = client.get("/api/v1/vehicles/MDHBN7AD0P0012345/report.pdf")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_history"


def test_invalid_vin_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/vehicles/NOT-A-VIN/report.pdf")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_vin"
