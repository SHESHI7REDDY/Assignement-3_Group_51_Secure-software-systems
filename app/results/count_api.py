"""Standalone results counting endpoint for fictional election fixture data.

Only administrators can trigger counting. Fixture input is deliberate and does
not accept untrusted client ballots; live integration requires reviewed adapter.
"""
import json
import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException

from app.results.audit import append_event, verify_audit
from app.results.audit_api import _require_admin
from app.results.preferential import count_preferential
from app.results.repository import ResultStorageError, get_count, save_count
from app.results.service import BallotValidationError
from app.results.elimination import EliminationError

router = APIRouter(tags=["results-count"])
FIXTURES = Path(__file__).parent / "fixtures"


@router.post("/count", status_code=201)
def calculate_result(x_results_admin_token: str | None = Header(default=None)):
    """Count a fixed fictional election exactly once and persist its result."""
    key, db = _require_admin(x_results_admin_token)
    if not verify_audit(key, db):
        raise HTTPException(409, "Audit integrity verification failed")
    try:
        election = json.loads((FIXTURES / "candidates.json").read_text(encoding="utf-8-sig"))
        ballots = json.loads((FIXTURES / "ballots.json").read_text(encoding="utf-8-sig"))
        election_id = election["election_id"]
        if get_count(election_id, db) is not None:
            raise HTTPException(409, "Results already counted for this election")
        result = count_preferential(election, ballots)
        save_count(result, db)
        append_event(election_id, "COUNT_COMPLETED", "local-demo-admin", "success", key, db)
    except (BallotValidationError, EliminationError, ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(422, "Invalid fictional election fixture or count") from exc
    except ResultStorageError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {**result, "status": "counted"}
