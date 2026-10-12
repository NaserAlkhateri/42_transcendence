import pytest

from app.services.vin import InvalidVinError, normalize_vin


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("JTDBR32E720123456", "JTDBR32E720123456"),
        ("jtdbr32e720123456", "JTDBR32E720123456"),
        ("  JTDBR32E720123456\n", "JTDBR32E720123456"),
        ("JTD BR32E7 2012-3456", "JTDBR32E720123456"),
        ("JTDBR32E72٠١٢٣٤٥٦", "JTDBR32E720123456"),  # Arabic-Indic digits from an Arabic keyboard
        ("JTDBR32E72۰۱۲۳۴۵۶", "JTDBR32E720123456"),  # Extended (Persian) Arabic-Indic digits
    ],
)
def test_normalize_vin_accepts_and_canonicalizes(raw: str, expected: str) -> None:
    assert normalize_vin(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "JTDBR32E72012345",  # 16 characters
        "JTDBR32E7201234567",  # 18 characters
        "JTDBR32E72O123456",  # letter O is never used in VINs
        "JTDBR32E72I123456",  # letter I
        "JTDBR32E72Q123456",  # letter Q
        "JTDBR32E72012345!",
        "ÉTDBR32E720123456",
    ],
)
def test_normalize_vin_rejects_invalid_input(raw: str) -> None:
    with pytest.raises(InvalidVinError, match="17"):
        normalize_vin(raw)
