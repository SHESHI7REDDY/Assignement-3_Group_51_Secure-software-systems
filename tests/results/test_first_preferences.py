"""RES-01 first-preference totals and rejection cases."""
import copy
import json
from pathlib import Path
import pytest
from app.results.counting import count_first_preferences
from app.results.service import BallotValidationError

FIXTURES = Path(__file__).resolve().parents[2] / 'app' / 'results' / 'fixtures'

@pytest.fixture
def sample():
    election = json.loads((FIXTURES / 'candidates.json').read_text(encoding='utf-8-sig'))
    ballots = json.loads((FIXTURES / 'ballots.json').read_text(encoding='utf-8-sig'))
    return election, ballots

def test_known_ten_ballot_first_preferences(sample):
    election, ballots = sample
    assert count_first_preferences(election, ballots) == {'CAND-A':4,'CAND-B':4,'CAND-C':2}

def test_count_is_repeatable_and_input_is_unchanged(sample):
    election, ballots = sample
    original = copy.deepcopy((election, ballots))
    assert count_first_preferences(election, ballots) == count_first_preferences(election, ballots)
    assert (election, ballots) == original

def test_empty_ballots_give_zero_totals(sample):
    election, ballots = sample
    ballots['ballots'] = []
    assert count_first_preferences(election, ballots) == {'CAND-A':0,'CAND-B':0,'CAND-C':0}

def test_unlisted_candidate_is_rejected(sample):
    election, ballots = sample
    ballots['ballots'][0]['preferences'][0] = 'UNKNOWN'
    with pytest.raises(BallotValidationError):
        count_first_preferences(election, ballots)

def test_duplicate_ballot_id_is_rejected(sample):
    election, ballots = sample
    ballots['ballots'][1]['ballot_id'] = ballots['ballots'][0]['ballot_id']
    with pytest.raises(BallotValidationError):
        count_first_preferences(election, ballots)

def test_mismatched_election_is_rejected(sample):
    election, ballots = sample
    ballots['election_id'] = 'OTHER'
    with pytest.raises(BallotValidationError):
        count_first_preferences(election, ballots)

def test_duplicate_candidate_definition_is_rejected(sample):
    election, ballots = sample
    election['candidates'][1]['candidate_id'] = 'CAND-A'
    with pytest.raises(BallotValidationError):
        count_first_preferences(election, ballots)
