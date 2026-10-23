"""Elimination decision for a fictional full-preference House election.

This module deliberately does not transfer ballots; that is the next milestone.
A tied last-place count raises an error instead of inventing a tie-break rule.
"""
from collections.abc import Mapping


class EliminationError(ValueError):
    """A deterministic, defensible exclusion cannot be made."""


class TiedLowestCandidates(EliminationError):
    """Multiple candidates share the lowest count."""


def select_candidate_to_eliminate(totals: Mapping[str, int]) -> str:
    """Return the unique lowest candidate when nobody has a majority.

    Args:
        totals: Counts for all currently continuing candidates.

    Raises:
        EliminationError: malformed totals, no votes, too few candidates,
            or a candidate has already won an outright majority.
        TiedLowestCandidates: two or more candidates are tied for last.
    """
    if not isinstance(totals, Mapping) or len(totals) < 2:
        raise EliminationError("At least two continuing candidates are required")
    if any(not isinstance(cid, str) or not cid for cid in totals):
        raise EliminationError("Candidate identifiers must be nonempty strings")
    if any(type(votes) is not int or votes < 0 for votes in totals.values()):
        raise EliminationError("Vote totals must be nonnegative integers")
    votes_cast = sum(totals.values())
    if votes_cast == 0:
        raise EliminationError("Cannot eliminate a candidate with zero ballots")
    if any(votes * 2 > votes_cast for votes in totals.values()):
        raise EliminationError("A candidate already has an outright majority")
    lowest = min(totals.values())
    tied = [candidate for candidate, count in totals.items() if count == lowest]
    if len(tied) != 1:
        raise TiedLowestCandidates("Lowest-ranked candidates are tied; manual resolution required")
    return tied[0]
