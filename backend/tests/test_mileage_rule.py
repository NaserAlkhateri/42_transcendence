from datetime import date

import pytest

from app.services.records import reading_is_inconsistent

JAN, MAR, JUN = date(2026, 1, 10), date(2026, 3, 10), date(2026, 6, 10)


@pytest.mark.parametrize(
    ("history", "service_date", "odometer_km", "flagged"),
    [
        ([], MAR, 5_000, False),  # first record for the VIN
        ([(JAN, 50_000)], MAR, 60_000, False),  # normal progress
        ([(JAN, 50_000)], MAR, 50_000, False),  # same reading is not a rollback
        ([(JAN, 50_000)], MAR, 40_000, True),  # lower than an earlier reading
        ([(MAR, 50_000)], MAR, 45_000, True),  # same day, recorded earlier with a higher reading
        # Compared with the HIGHEST earlier reading: a second rollback can't hide behind a flagged one.
        ([(JAN, 120_000), (MAR, 88_000)], JUN, 100_000, True),
        ([(JUN, 70_000)], MAR, 80_000, True),  # back-dated entry higher than a later reading
        ([(JAN, 50_000), (JUN, 70_000)], MAR, 60_000, False),  # back-dated entry that fits
    ],
)
def test_reading_is_flagged_when_it_does_not_fit_the_effective_history(history, service_date, odometer_km, flagged):
    assert reading_is_inconsistent(history, service_date, odometer_km) is flagged
