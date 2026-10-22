
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List
import json

from database import SessionLocal, StoredBallot
from security import encrypt_ballot
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="Ballot Casting & Privacy Module")

app.mount("/static", StaticFiles(directory="static"), name="static")

# Mock candidates for the House of Representatives ballot
candidates = [
    {"candidate_id": "CAND-001", "name": "Candidate A"},
    {"candidate_id": "CAND-002", "name": "Candidate B"},
    {"candidate_id": "CAND-003", "name": "Candidate C"},
    {"candidate_id": "CAND-004", "name": "Candidate D"},
]


class Preference(BaseModel):
    candidate_id: str
    rank: int


class BallotSubmission(BaseModel):
    election_id: str
    preferences: List[Preference]


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/candidates")
def get_candidates():
    return {
        "election_id": "ELECTION-2026",
        "candidates": candidates
    }

def verify_mock_authorisation(
    x_auth_token: str = Header(None),
    x_mock_role: str = Header(None)
):
    if x_auth_token != "ballot-demo-token":
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing authentication token."
        )

    if x_mock_role != "voter":
        raise HTTPException(
            status_code=403,
            detail="Only authorised voters can submit ballots."
        )
@app.post("/ballots")
def submit_ballot(
    ballot: BallotSubmission,
    x_auth_token: str = Header(None),
    x_mock_role: str = Header(None)
):
    verify_mock_authorisation(x_auth_token, x_mock_role)

    # Check number of preferences
    if len(ballot.preferences) != len(candidates):
        raise HTTPException(
            status_code=400,
            detail="All candidates must receive a preference."
        )

    candidate_ids = [p.candidate_id for p in ballot.preferences]
    ranks = [p.rank for p in ballot.preferences]

    valid_candidate_ids = [c["candidate_id"] for c in candidates]

    # Reject unknown or duplicate candidates
    if len(set(candidate_ids)) != len(candidate_ids):
        raise HTTPException(
            status_code=400,
            detail="Duplicate candidate detected."
        )

    if set(candidate_ids) != set(valid_candidate_ids):
        raise HTTPException(
            status_code=400,
            detail="Invalid candidate detected."
        )

    # Rankings must be 1, 2, 3, 4 exactly once
    expected_ranks = list(range(1, len(candidates) + 1))

    if sorted(ranks) != expected_ranks:
        raise HTTPException(
            status_code=400,
            detail="Preferences must contain each rank exactly once."
        )

    # Convert anonymous ballot preferences to JSON
    ballot_data = {
        "preferences": [
            {
                "candidate_id": p.candidate_id,
                "rank": p.rank
            }
            for p in ballot.preferences
        ]
    }

    ballot_json = json.dumps(ballot_data)

    # Encrypt ballot before database storage
    encrypted_data = encrypt_ballot(ballot_json)

    db = SessionLocal()

    try:
        stored_ballot = StoredBallot(
            election_id=ballot.election_id,
            encrypted_ballot=encrypted_data
        )

        db.add(stored_ballot)
        db.commit()
        db.refresh(stored_ballot)

    finally:
        db.close()

    return {
        "message": "Ballot accepted and securely stored",
        "ballot_id": stored_ballot.id,
        "election_id": ballot.election_id
    }
