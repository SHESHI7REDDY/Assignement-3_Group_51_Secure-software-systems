"""Ballot APIs use the real login session and server-controlled voter link."""
from fastapi import APIRouter, Depends, HTTPException

from app.auth.repository import get_user_by_id
from app.auth.profiles import identity_for_user
from app.auth.router import SessionDependency
from app.eligibility.config import Settings, get_settings
from . import integration
from .schemas import BallotSubmission

router = APIRouter(prefix="/ballots", tags=["Ballot Casting"])


def require_linked_voter(session: SessionDependency):
    user = get_user_by_id(session[0])
    if user is None:
        raise HTTPException(401, "Invalid account")
    identity = identity_for_user(user)
    if identity["role"] != "voter":
        raise HTTPException(403, "Only voters can submit ballots")
    if not identity["voter_id"]:
        raise HTTPException(403, "Account has no verified voter link")
    return identity


@router.get("/candidates")
def get_candidates(settings: Settings = Depends(get_settings),
                   candidate_db_path=Depends(integration.get_candidate_db_path)):
    return integration.catalog(settings, candidate_db_path)


@router.post("/validate")
def validate_submitted_ballot(ballot: BallotSubmission,
                              identity=Depends(require_linked_voter),
                              settings: Settings = Depends(get_settings),
                              candidate_db_path=Depends(integration.get_candidate_db_path)):
    from contextlib import closing
    with closing(integration.open_connection(settings, candidate_db_path)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            integration.require_open(connection, settings, ballot)
        finally:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
    return {"message": "Ballot validation successful", "election_id": ballot.election_id}


@router.post("/submit")
def submit_ballot(ballot: BallotSubmission,
                  identity=Depends(require_linked_voter),
                  settings: Settings = Depends(get_settings),
                  candidate_db_path=Depends(integration.get_candidate_db_path)):
    return integration.submit(ballot, identity, settings, candidate_db_path)
