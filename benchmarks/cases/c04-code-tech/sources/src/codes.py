"""Fictitious locker code service (implementation evidence snapshot)."""
import secrets

EXPIRY_HOURS = 48


def generate_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def is_expired(age_hours: float) -> bool:
    return age_hours >= EXPIRY_HOURS
