"""Deterministic preferential counting for fictional, fully ranked House ballots.

A tied exclusion is deliberately unresolved; real election tie procedures are
not modeled by this small educational prototype.
"""
from collections.abc import Mapping

from app.results.counting import count_first_preferences
from app.results.elimination import select_candidate_to_eliminate
from app.results.service import BallotValidationError, validate_ballot


def count_preferential(election: Mapping, ballot_batch: Mapping) -> dict:
    """Return a winner and verifiable round-by-round count without voter data.

    Refuses zero-ballot elections and unresolved elimination ties. Requires full
    rankings of every candidate. Inputs are not mutated.
    """
    first = count_first_preferences(election, ballot_batch)
    if sum(first.values()) == 0:
        raise BallotValidationError("Cannot count an election with no ballots")

    election_id = election["election_id"]
    candidate_ids = tuple(first)
    ballots = [
        validate_ballot(ballot, election_id, candidate_ids, ballot_batch["election_id"])
        for ballot in ballot_batch["ballots"]
    ]
    continuing = set(candidate_ids)
    rounds = []
    while True:
        totals = {cid: 0 for cid in candidate_ids if cid in continuing}
        for preferences in ballots:
            selected = next(cid for cid in preferences if cid in continuing)
            totals[selected] += 1
        total = sum(totals.values())
        round_record = {"round": len(rounds) + 1, "totals": totals, "eliminated": None}
        winners = [cid for cid, n in totals.items() if n * 2 > total]
        if winners:
            rounds.append(round_record)
            return {
                "election_id": election_id,
                "total_ballots": len(ballots),
                "winner_id": winners[0],
                "rounds": rounds,
            }
        excluded = select_candidate_to_eliminate(totals)
        round_record["eliminated"] = excluded
        rounds.append(round_record)
        continuing.remove(excluded)
