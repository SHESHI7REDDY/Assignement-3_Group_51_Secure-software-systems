from fastapi import HTTPException

from .schemas import BallotSubmission
import json
from pathlib import Path

from cryptography.fernet import Fernet

VALID_CANDIDATES = {
    "CAND-001",
    "CAND-002",
    "CAND-003",
    "CAND-004"
}


def validate_ballot(ballot: BallotSubmission) -> None:
    if len(ballot.preferences) != len(VALID_CANDIDATES):
        raise HTTPException(
            status_code=400,
            detail="All candidates must receive a preference."
        )

    candidate_ids = [
        preference.candidate_id
        for preference in ballot.preferences
    ]

    ranks = [
        preference.rank
        for preference in ballot.preferences
    ]

    if len(set(candidate_ids)) != len(candidate_ids):
        raise HTTPException(
            status_code=400,
            detail="Duplicate candidate detected."
        )

    if set(candidate_ids) != VALID_CANDIDATES:
        raise HTTPException(
            status_code=400,
            detail="Invalid candidate detected."
        )

    expected_ranks = list(
        range(1, len(VALID_CANDIDATES) + 1)
    )

    if sorted(ranks) != expected_ranks:
        raise HTTPException(
            status_code=400,
            detail="Preferences must contain each rank exactly once."
        )
def verify_voter_authorisation(
    auth_token: str | None,
    role: str | None
) -> None:
    if auth_token != "ballot-demo-token":
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing authentication token."
        )

    if role != "voter":
        raise HTTPException(
            status_code=403,
            detail="Only authorised voters can submit ballots."
        )
KEY_FILE = Path("data/ballot_key.key")


def load_or_create_key() -> bytes:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)

    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()

    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key


cipher = Fernet(load_or_create_key())


def encrypt_ballot(ballot: BallotSubmission) -> str:
    ballot_data = {
        "preferences": [
            {
                "candidate_id": preference.candidate_id,
                "rank": preference.rank
            }
            for preference in ballot.preferences
        ]
    }

    ballot_json = json.dumps(ballot_data)

    encrypted_value = cipher.encrypt(
        ballot_json.encode("utf-8")
    )

    return encrypted_value.decode("utf-8")