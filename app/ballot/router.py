from fastapi import APIRouter

from .schemas import BallotSubmission
from .service import validate_ballot


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