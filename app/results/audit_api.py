"""Administrative audit read and verification endpoints for the local prototype.

The local stand-in credential is configured through RESULTS_ADMIN_TOKEN. Replace
it with the team's verified authentication system before deployment/integration.
"""
import hmac
import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException

from app.results.audit import read_events, verify_audit
from app.results.repository import DEFAULT_DB_PATH

router = APIRouter(tags=["results-audit"])


def _configuration() -> tuple[bytes, Path]:
    token = os.getenv("RESULTS_ADMIN_TOKEN", "")
    key = os.getenv("RESULTS_AUDIT_HMAC_KEY", "")
    if not token or len(token) < 16 or not key:
        raise HTTPException(503, "Audit administration not configured")
    try:
        key_bytes = bytes.fromhex(key)
    except ValueError:
        raise HTTPException(503, "Audit administration not configured") from None
    if len(key_bytes) < 32:
        raise HTTPException(503, "Audit administration not configured")
    path = Path(os.environ.get("RESULTS_DB_PATH", str(DEFAULT_DB_PATH)))
    return key_bytes, path


def _require_admin(token: str | None):
    # Fail closed when configuration is missing; do not log secret material.
    key, db = _configuration()
    if token is None:
        raise HTTPException(401, "Administrator credential required")
    if not hmac.compare_digest(token, os.environ["RESULTS_ADMIN_TOKEN"]):
        raise HTTPException(403, "Administrator access required")
    return key, db


@router.get("/{election_id}/audit/verify")
def verify_election_audit(election_id: str, x_results_admin_token: str | None = Header(default=None)):
    key, db = _require_admin(x_results_admin_token)
    # Audit entries form one global chain; verify all events, not just this election.
    valid = verify_audit(key, db)
    return {"election_id": election_id, "integrity_valid": valid,
            "scope": "global_chain", "events_for_election": len(read_events(db, election_id=election_id))}


@router.get("/{election_id}/audit")
def get_election_audit(election_id: str, x_results_admin_token: str | None = Header(default=None)):
    key, db = _require_admin(x_results_admin_token)
    if not verify_audit(key, db):
        raise HTTPException(409, "Audit integrity verification failed")
    events = read_events(db, election_id=election_id)
    # Avoid exposing actor identifiers and internal HMAC linkage unnecessarily.
    return {"election_id": election_id,
            "events": [{"sequence": e["sequence"], "event_type": e["event_type"],
                        "outcome": e["outcome"], "occurred_at": e["occurred_at"]}
                       for e in events]}
