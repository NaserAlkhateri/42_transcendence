import re

# Same rule as the database CHECK constraint ck_vehicles_vin_format.
VIN_PATTERN = re.compile(r"[A-HJ-NPR-Z0-9]{17}")
_VIN_FRAGMENT = re.compile(r"[A-HJ-NPR-Z0-9]{0,17}")
_SEPARATORS = re.compile(r"[\s-]+")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


class InvalidVinError(ValueError):
    """The input cannot be normalized into a valid 17-character VIN."""


def normalize_vin(raw: str) -> str:
    """Return the canonical VIN: separators removed, Arabic-Indic digits mapped to 0-9, upper case,
    exactly 17 of A-Z/0-9 without I, O or Q.

    The ISO 3779 check digit is deliberately not enforced: it is mandatory only for North American
    VINs, and GCC-market imports from Japan or Europe legitimately fail it.
    """
    vin = _SEPARATORS.sub("", raw).translate(_ARABIC_DIGITS).upper()
    if not VIN_PATTERN.fullmatch(vin):
        raise InvalidVinError("A VIN has exactly 17 letters or digits and never contains I, O or Q.")
    return vin


def normalize_vin_fragment(raw: str) -> str:
    """Part of a VIN typed into a search box, normalized like `normalize_vin` but 0 to 17 characters long.
    Blank input gives ""."""
    fragment = _SEPARATORS.sub("", raw).translate(_ARABIC_DIGITS).upper()
    if not _VIN_FRAGMENT.fullmatch(fragment):
        raise InvalidVinError("Enter up to 17 letters or digits of the VIN. A VIN never contains I, O or Q.")
    return fragment
