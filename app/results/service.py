"""Ballot validation for fictional full-preference House elections."""
from collections.abc import Mapping

class BallotValidationError(ValueError):
    """Invalid ballot or mismatching election."""

def validate_ballot(ballot: Mapping, election_id: str, candidate_ids, ballot_election_id=None):
    """Return an immutable validated preference order; never processes voter identities."""
    if not isinstance(ballot, Mapping):
        raise BallotValidationError('Ballot must be an object')
    if not isinstance(election_id, str) or not election_id:
        raise BallotValidationError('Invalid election ID')
    if ballot.get('election_id', ballot_election_id) != election_id:
        raise BallotValidationError('Wrong election ID')
    if not isinstance(candidate_ids, (list, tuple, set)) or not candidate_ids:
        raise BallotValidationError('Candidate list is invalid')
    if len(set(candidate_ids)) != len(candidate_ids):
        raise BallotValidationError('Candidate IDs are duplicated')
    preferences = ballot.get('preferences')
    if not isinstance(preferences, list):
        raise BallotValidationError('Preferences must be a list')
    if any(not isinstance(x, str) for x in preferences):
        raise BallotValidationError('Preferences must be strings')
    if len(preferences) != len(candidate_ids):
        raise BallotValidationError('Incomplete preference ranking')
    if len(set(preferences)) != len(preferences):
        raise BallotValidationError('Duplicate preferences')
    if set(preferences) != set(candidate_ids):
        raise BallotValidationError('Unknown candidate or missing candidate')
    return tuple(preferences)
