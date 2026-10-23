from fastapi import HTTPException

from .schemas import BallotSubmission


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