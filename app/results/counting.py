"""First-preference counting for the standalone fictional election prototype.

This module does not declare a winner or redistribute preferences yet.
"""
from collections.abc import Mapping
from app.results.service import BallotValidationError, validate_ballot


def count_first_preferences(election: Mapping, ballot_batch: Mapping) -> dict[str, int]:
    """Validate anonymous ballots, then total the first preferences.

    Preserves candidate order from the election fixture. Raises
    BallotValidationError rather than silently skipping malformed ballots.
    """
    if not isinstance(election, Mapping) or not isinstance(ballot_batch, Mapping):
        raise BallotValidationError("Election and ballot batch must be objects")
    election_id = election.get("election_id")
    if not isinstance(election_id, str) or not election_id:
        raise BallotValidationError("Missing election ID")
    if ballot_batch.get("election_id") != election_id:
        raise BallotValidationError("Ballot batch belongs to a different election")
    candidates = election.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise BallotValidationError("Candidate list must be nonempty")
    if any(not isinstance(item, Mapping) or not isinstance(item.get("candidate_id"), str)
           or not item.get("candidate_id") for item in candidates):
        raise BallotValidationError("Invalid candidate entry")
    candidate_ids = [item["candidate_id"] for item in candidates]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise BallotValidationError("Duplicate candidate IDs")
    ballots = ballot_batch.get("ballots")
    if not isinstance(ballots, list):
        raise BallotValidationError("Ballots must be a list")
    seen_ids: set[str] = set()
    totals = {cid: 0 for cid in candidate_ids}
    for ballot in ballots:
        if not isinstance(ballot, Mapping):
            raise BallotValidationError("Invalid ballot object")
        ballot_id = ballot.get("ballot_id")
        if not isinstance(ballot_id, str) or not ballot_id or ballot_id in seen_ids:
            raise BallotValidationError("Missing or duplicated ballot ID")
        seen_ids.add(ballot_id)
        preferences = validate_ballot(ballot, election_id, candidate_ids, ballot_batch["election_id"])
        totals[preferences[0]] += 1
    return totals
