"""Full preferential-count examples, failure conditions, and privacy checks."""
import copy
import json
from pathlib import Path

import pytest

from app.results.elimination import TiedLowestCandidates
from app.results.preferential import count_preferential
from app.results.service import BallotValidationError

FIXTURES = Path(__file__).resolve().parents[2] / 'app' / 'results' / 'fixtures'


def load():
    election = json.loads((FIXTURES / 'candidates.json').read_text(encoding='utf-8-sig'))
    ballots = json.loads((FIXTURES / 'ballots.json').read_text(encoding='utf-8-sig'))
    return election, ballots


def test_demo_count_has_expected_winner_and_rounds():
    election, ballots = load()
    result = count_preferential(election, ballots)
    assert result['winner_id'] == 'CAND-A'
    assert result['election_id'] == 'DEMO-001'
    assert result['total_ballots'] == 10
    assert result['rounds'] == [
        {'round': 1, 'totals': {'CAND-A': 4, 'CAND-B': 4, 'CAND-C': 2}, 'eliminated': 'CAND-C'},
        {'round': 2, 'totals': {'CAND-A': 6, 'CAND-B': 4}, 'eliminated': None},
    ]


def test_first_round_majority_does_not_eliminate_anyone():
    election, ballots = load()
    ballots['ballots'] = ballots['ballots'][:4] + ballots['ballots'][8:9]
    result = count_preferential(election, ballots)
    assert result['winner_id'] == 'CAND-A'
    assert len(result['rounds']) == 1


def test_deterministic_and_input_unchanged():
    election, ballots = load()
    original = copy.deepcopy((election, ballots))
    assert count_preferential(election, ballots) == count_preferential(election, ballots)
    assert (election, ballots) == original


def test_zero_ballots_rejected():
    election, ballots = load()
    ballots['ballots'] = []
    with pytest.raises(BallotValidationError):
        count_preferential(election, ballots)


def test_duplicate_ballot_id_rejected():
    election, ballots = load()
    ballots['ballots'][1]['ballot_id'] = ballots['ballots'][0]['ballot_id']
    with pytest.raises(BallotValidationError):
        count_preferential(election, ballots)


def test_invalid_ranking_rejected():
    election, ballots = load()
    ballots['ballots'][0]['preferences'] = ['CAND-A', 'CAND-A', 'CAND-B']
    with pytest.raises(BallotValidationError):
        count_preferential(election, ballots)


def test_last_place_tie_is_explicit_error():
    election, ballots = load()
    ballots['ballots'] = ballots['ballots'][:1] + ballots['ballots'][4:5] + ballots['ballots'][8:9]
    with pytest.raises(TiedLowestCandidates):
        count_preferential(election, ballots)


def test_results_do_not_contain_voter_details():
    election, ballots = load()
    result = count_preferential(election, ballots)
    assert 'voter_id' not in json.dumps(result)
    assert 'ballot_id' not in json.dumps(result)
    assert 'preferences' not in json.dumps(result)
