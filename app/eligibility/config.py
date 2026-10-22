"""Configuration for the eligibility module (owner: Ved).

Secrets are read from environment variables only (never hard-coded).
If a secret is missing in development, a random per-process value is
generated so the module still runs, and a warning is logged.
"""
from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache

from app.shared.config import DATA

log = logging.getLogger("eligibility.config")


def _secret(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    log.warning("%s not set - using a random development value", name)
    return secrets.token_hex(32)


@dataclass(frozen=True)
class Settings:
    db_path: str = field(default_factory=lambda: os.getenv("ELIG_DB_PATH", str(DATA / "eligibility.db")))
    election_id: str = field(default_factory=lambda: os.getenv("ELECTION_ID", "FED-2026"))
    election_date: date = field(
        default_factory=lambda: date.fromisoformat(os.getenv("ELECTION_DATE", "2026-12-05"))
    )
    # Mock auth is OFF by default (fail closed). Only the standalone demo
    # (app/eligibility/standalone.py) and the tests switch it on.
    # Integrated: set ELIG_AUTH_VERIFY_URL to Varshil's /auth/verify.
    mock_auth: bool = field(default_factory=lambda: os.getenv("ELIG_MOCK_AUTH", "0") == "1")
    auth_verify_url: str | None = field(default_factory=lambda: os.getenv("ELIG_AUTH_VERIFY_URL"))
    auth_secret: str = field(default_factory=lambda: _secret("ELIG_AUTH_SECRET"))
    pseudonym_key: str = field(default_factory=lambda: _secret("ELIG_PSEUDONYM_KEY"))
    ballot_token_ttl_seconds: int = 900
    access_token_ttl_seconds: int = 1800


@lru_cache
def get_settings() -> Settings:
    """FastAPI dependency. Tests replace it with app.dependency_overrides."""
    return Settings()
