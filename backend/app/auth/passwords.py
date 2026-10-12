"""Argon2id password hashing."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # argon2-cffi defaults: Argon2id with RFC 9106 parameters


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


_dummy_hash: str | None = None


def burn_verify_time(password: str) -> None:
    """Spend the same Argon2 work as a real check, so unknown emails can't be told apart by response time."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("sijil-timing-equalizer")
    verify_password(_dummy_hash, password)
