"""Trusted identity verification and election-scoped permissions."""

import os
from urllib.parse import urlparse

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Optional


bearer = HTTPBearer(auto_error=False)


class Identity(BaseModel):
    model_config = ConfigDict(strict=True)

    user_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    managed_election_ids: list[str] = Field(default_factory=list)


def fetch_identity(token: str) -> Identity:
    url = os.getenv("CAND_AUTH_VERIFY_URL", "").strip()
    parsed = urlparse(url)

    local_http = (
        parsed.scheme == "http"
        and parsed.hostname in ("127.0.0.1", "localhost", "::1")
    )

    if not parsed.hostname or not (
        parsed.scheme == "https" or local_http
    ):
        raise HTTPException(
            503, "Trusted authentication service not configured"
        )

    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise HTTPException(
            503, "Invalid authentication service configuration"
        )

    try:
        with httpx.Client(
            timeout=3.0,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError:
        raise HTTPException(
            503, "Authentication service unavailable"
        )

    if response.status_code in (401, 403):
        raise HTTPException(
            401,
            "Invalid or expired credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if response.status_code != 200:
        raise HTTPException(
            503, "Authentication verification failed"
        )

    try:
        return Identity.model_validate(response.json())
    except (ValueError, ValidationError):
        raise HTTPException(
            503, "Invalid authentication service response"
        )


def get_identity(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> Identity:
    if credentials is None:
        raise HTTPException(
            401,
            "Bearer credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return fetch_identity(credentials.credentials)


def require_candidate_manager(
    identity: Identity = Depends(get_identity),
) -> Identity:
    if identity.role != "officer":
        raise HTTPException(
            403, "Candidate management permission required"
        )

    return identity


def ensure_election_permission(
    identity: Identity,
    election_id: str,
) -> None:
    if (
        identity.role != "officer"
        or election_id not in identity.managed_election_ids
    ):
        raise HTTPException(
            403, "Not permitted to manage this election"
        )