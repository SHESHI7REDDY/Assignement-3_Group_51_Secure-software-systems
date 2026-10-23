"""Combined application results: real sessions, closed election, accepted ballots."""
from fastapi import APIRouter, Depends, HTTPException

from app.auth.router import AdminDependency
from app.ballot.integration import get_candidate_db_path
from app.eligibility.config import Settings, get_settings
from . import audit, platform

router = APIRouter(prefix="/results", tags=["Integrated results and audit"])


def _election(election_id, settings):
    if election_id != settings.election_id:
        raise HTTPException(404, "Election not found")


@router.post("/count", status_code=201)
def count(admin: AdminDependency, settings: Settings = Depends(get_settings),
          candidate_path=Depends(get_candidate_db_path)):
    key, db = platform.configuration()
    return platform.operation(platform.count, db, settings, candidate_path, settings, str(admin["id"]), key)


@router.post("/{election_id}/publish")
def publish(election_id: str, admin: AdminDependency, settings: Settings = Depends(get_settings),
            candidate_path=Depends(get_candidate_db_path)):
    _election(election_id, settings)
    key, db = platform.configuration()
    return platform.operation(platform.publish, db, settings, candidate_path, election_id, str(admin["id"]), key)


@router.get("/{election_id}/audit/verify")
def verify(election_id: str, admin: AdminDependency, settings: Settings = Depends(get_settings),
           candidate_path=Depends(get_candidate_db_path)):
    _election(election_id, settings)
    key, db = platform.configuration()
    def read(connection):
        return {"election_id": election_id, "integrity_valid": audit.verify_audit(key, connection=connection),
                "scope": "global_results_chain", "events_for_election": len(audit.read_events(election_id=election_id, connection=connection))}
    return platform.operation(read, db, settings, candidate_path)


@router.get("/{election_id}/audit")
def events(election_id: str, admin: AdminDependency, settings: Settings = Depends(get_settings),
           candidate_path=Depends(get_candidate_db_path)):
    _election(election_id, settings)
    key, db = platform.configuration()
    def read(connection):
        platform.ensure_audit(connection, key)
        rows = audit.read_events(election_id=election_id, connection=connection)
        return {"election_id": election_id, "events": [
            {name: row[name] for name in ("sequence", "event_type", "outcome", "occurred_at")} for row in rows]}
    return platform.operation(read, db, settings, candidate_path)


@router.get("/{election_id}")
def public(election_id: str, settings: Settings = Depends(get_settings),
           candidate_path=Depends(get_candidate_db_path)):
    _election(election_id, settings)
    key, db = platform.configuration()
    return platform.operation(platform.public_result, db, settings, candidate_path, election_id, key)
