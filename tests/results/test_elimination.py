"""Tests for an elimination decision, without preference transfers."""
import pytest

from app.results.elimination import (
    EliminationError,
    TiedLowestCandidates,
    select_candidate_to_eliminate,
)


def test_selects_c_from_known_first_round():
    assert select_candidate_to_eliminate({'CAND-A': 4, 'CAND-B': 4, 'CAND-C': 2}) == 'CAND-C'


def test_no_order_dependence():
    totals = {'CAND-C': 2, 'CAND-B': 4, 'CAND-A': 4}
    saved = totals.copy()
    assert select_candidate_to_eliminate(totals) == 'CAND-C'
    assert totals == saved


def test_tied_lowest_requires_resolution():
    with pytest.raises(TiedLowestCandidates, match='tied'):
        select_candidate_to_eliminate({'A': 5, 'B': 3, 'C': 3})


def test_all_tied_requires_resolution():
    with pytest.raises(TiedLowestCandidates):
        select_candidate_to_eliminate({'A': 3, 'B': 3})


def test_existing_majority_prevents_elimination():
    with pytest.raises(EliminationError, match='majority'):
        select_candidate_to_eliminate({'A': 6, 'B': 4, 'C': 0})


@pytest.mark.parametrize('totals', [
    {}, {'A': 1}, {'A': 0, 'B': 0},
    {'A': -1, 'B': 2}, {'A': 2.5, 'B': 3},
    {'A': True, 'B': 1}, {'': 2, 'B': 3},
    {'A': '2', 'B': 3},
])
def test_bad_count_data_is_rejected(totals):
    with pytest.raises(EliminationError):
        select_candidate_to_eliminate(totals)
