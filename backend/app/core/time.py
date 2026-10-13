from datetime import date, datetime, timedelta, timezone

# The UAE has no daylight saving: Gulf Standard Time is always UTC+4.
UAE_TIME = timezone(timedelta(hours=4), "GST")


def uae_now() -> datetime:
    return datetime.now(UAE_TIME)


def uae_today() -> date:
    return uae_now().date()
