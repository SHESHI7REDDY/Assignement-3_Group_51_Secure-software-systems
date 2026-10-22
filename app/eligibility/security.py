"""Authentication, authorisation and cryptographic helpers (ELIG-03, ELIG-04).

Access tokens: in standalone mode this module verifies HMAC-SHA256 signed
mock tokens (same claims Varshil's /auth/verify returns: user_id, role,
voter_id). In integration mode it calls the Authentication module instead.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from .config import Settings, get_settings

ROLES = {"voter", "officer", "service"}


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str
    voter_id: str | None = None


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue_mock_token(settings: Settings, user_id: str, role: str, voter_id: str | None,
                     ttl: int | None = None) -> str:
    if role not in ROLES:
        raise ValueError("unknown role")
    claims = {"sub": user_id, "role": role, "voter_id": voter_id,
              "exp": int(time.time()) + (ttl if ttl is not None else settings.access_token_ttl_seconds)}
    body = _b64e(json.dumps(claims, separators=(",", ":")).encode())
    sig = _b64e(hmac.new(settings.auth_secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_mock_token(settings: Settings, token: str) -> Principal:
    try:
        body, sig = token.split(".")
        expected = _b64e(hmac.new(settings.auth_secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):  # constant-time comparison
            raise ValueError("bad signature")
        claims = json.loads(_b64d(body))
        if int(claims["exp"]) < time.time():
            raise ValueError("expired")
        if claims["role"] not in ROLES:
            raise ValueError("bad role")
        return Principal(claims["sub"], claims["role"], claims.get("voter_id"))
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


def verify_remote_token(settings: Settings, token: str) -> Principal:
    url = settings.auth_verify_url or ""
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        # Only http(s) is allowed - blocks file:// or custom schemes (Bandit B310 / CWE-22)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth service not configured")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:  # nosec B310 - scheme validated above
            data = json.loads(resp.read())
        if data.get("role") not in ROLES:
            raise ValueError
        return Principal(data["user_id"], data["role"], data.get("voter_id"))
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


def get_principal(request: Request, settings: Settings = Depends(get_settings)) -> Principal:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token",
                            headers={"WWW-Authenticate": "Bearer"})
    token = header[7:].strip()
    if settings.mock_auth:
        return verify_mock_token(settings, token)
    return verify_remote_token(settings, token)


def require_roles(*roles: str):
    def checker(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted for this role")
        return principal
    return checker


def ensure_self_or_officer(principal: Principal, voter_id: str) -> None:
    """Object-level authorisation: stops a voter reading/acting on another
    voter's record by changing the ID in the request (IDOR)."""
    if principal.role == "officer":
        return
    if principal.role == "voter" and principal.voter_id is not None \
            and hmac.compare_digest(principal.voter_id, voter_id):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only access your own enrolment")


def pseudonymise(settings: Settings, value: str) -> str:
    """Keyed hash so audit entries never contain a raw voter ID."""
    return hmac.new(settings.pseudonym_key.encode(), value.encode(), hashlib.sha256).hexdigest()[:20]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
