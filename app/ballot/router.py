from fastapi import APIRouter, Header

from .repository import initialise_database, save_ballot
from .schemas import BallotSubmission
from .service import (
    encrypt_ballot,
    validate_ballot,
    verify_voter_authorisation,
)

router = APIRouter(
    prefix="/ballots",
    tags=["Ballot Casting"]
)


CANDIDATES = [
    {"candidate_id": "CAND-001", "name": "Candidate A"},
    {"candidate_id": "CAND-002", "name": "Candidate B"},
    {"candidate_id": "CAND-003", "name": "Candidate C"},
    {"candidate_id": "CAND-004", "name": "Candidate D"},
]


@router.get("/candidates")
def get_candidates():
    return {
        "election_id": "ELECTION-2026",
        "candidates": CANDIDATES
    }


@router.post("/validate")
def validate_submitted_ballot(ballot: BallotSubmission):
    validate_ballot(ballot)

    return {
        "message": "Ballot validation successful",
        "election_id": ballot.election_id
    }
@router.post("/submit")
@router.post("/submit")
def submit_ballot(
    ballot: BallotSubmission,
    x_auth_token: str | None = Header(default=None),
    x_mock_role: str | None = Header(default=None)
):
    verify_voter_authorisation(
        x_auth_token,
        x_mock_role
    )

    validate_ballot(ballot)

    initialise_database()

    encrypted_value = encrypt_ballot(ballot)

    ballot_id = save_ballot(
        election_id=ballot.election_id,
        encrypted_ballot=encrypted_value
    )

    return {
        "message": "Ballot accepted and securely stored",
        "ballot_id": ballot_id,
        "election_id": ballot.election_id
    }