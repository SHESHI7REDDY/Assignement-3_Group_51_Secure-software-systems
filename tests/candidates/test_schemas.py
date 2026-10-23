import pytest
from pydantic import ValidationError

from app.candidates.schemas import CandidateCreate


def valid_candidate():
    return {
        "election_id": "ELECTION-2026",
        "name": "Alex O'Brien",
        "party": "Independent",
        "ballot_order": 1,
    }


def test_valid_candidate_is_accepted():
    candidate = CandidateCreate(**valid_candidate())

    assert candidate.name == "Alex O'Brien"
    assert candidate.ballot_order == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"name": ""},
        {"name": "   "},
        {"name": "A" * 121},
        {"party": ""},
        {"election_id": "invalid election id"},
        {"ballot_order": 0},
        {"ballot_order": 1001},
        {"ballot_order": "1"},
        {"ballot_order": True},
        {"unexpected_field": "value"},
    ],
)
def test_invalid_candidate_is_rejected(changes):
    payload = valid_candidate()
    payload.update(changes)

    with pytest.raises(ValidationError):
        CandidateCreate(**payload)


def test_missing_name_is_rejected():
    payload = valid_candidate()
    del payload["name"]

    with pytest.raises(ValidationError):
        CandidateCreate(**payload)


def test_surrounding_whitespace_is_removed():
    payload = valid_candidate()
    payload["name"] = "  Shashi "

    candidate = CandidateCreate(**payload)

    assert candidate.name == "Shashi"