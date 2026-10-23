"""Executable RES-01 ballot validation tests."""
import json
from pathlib import Path
import pytest
from app.results.service import validate_ballot, BallotValidationError

CANDIDATES = ['CAND-A', 'CAND-B', 'CAND-C']

def check(preferences, election='DEMO-001'):
    return validate_ballot({'preferences': preferences}, 'DEMO-001', CANDIDATES, election)

def test_valid_ranked_ballot():
    assert check(CANDIDATES) == tuple(CANDIDATES)

@pytest.mark.parametrize('preferences', [
    ['CAND-A','CAND-A','CAND-B'],
    ['CAND-A','CAND-B','UNKNOWN'],
    ['CAND-A','CAND-B'],
    [],
    ['CAND-A',None,'CAND-C'],
    'CAND-A,CAND-B,CAND-C',
])
def test_invalid_preferences_rejected(preferences):
    with pytest.raises(BallotValidationError):
        check(preferences)

def test_wrong_election_rejected():
    with pytest.raises(BallotValidationError):
        check(CANDIDATES, 'OTHER-001')

def test_all_sample_ballots_validate():
    root = Path(__file__).resolve().parents[2] / 'app' / 'results' / 'fixtures'
    ballots = json.loads((root/'ballots.json').read_text(encoding='utf-8-sig'))
    candidates = json.loads((root/'candidates.json').read_text(encoding='utf-8-sig'))
    ids = [x['candidate_id'] for x in candidates['candidates']]
    assert ballots['election_id'] == candidates['election_id']
    assert len(ballots['ballots']) == 10
    for ballot in ballots['ballots']:
        assert 'voter_id' not in ballot
        assert len(validate_ballot(ballot, ballots['election_id'], ids, ballots['election_id'])) == 3
