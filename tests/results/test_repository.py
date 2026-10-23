"""SQLite count snapshot tests use a temporary DB; no shared files mutated."""
import copy
import json
import sqlite3
from pathlib import Path

import pytest

from app.results.preferential import count_preferential
from app.results.repository import (
    ResultStorageError, get_count, initialize_database, save_count,
)

FIXTURES = Path(__file__).resolve().parents[2] / 'app' / 'results' / 'fixtures'


@pytest.fixture
def result():
    election = json.loads((FIXTURES / 'candidates.json').read_text(encoding='utf-8-sig'))
    ballots = json.loads((FIXTURES / 'ballots.json').read_text(encoding='utf-8-sig'))
    return count_preferential(election, ballots)


def test_database_initialization_is_idempotent(tmp_path):
    path = tmp_path / 'nested' / 'results.db'
    initialize_database(path)
    initialize_database(path)
    assert path.is_file()


def test_save_and_read_result(tmp_path, result):
    path = tmp_path / 'results.db'
    save_count(result, path)
    saved = get_count('DEMO-001', path)
    assert saved['winner_id'] == 'CAND-A'
    assert saved['total_ballots'] == 10
    assert saved['rounds'] == result['rounds']
    assert saved['status'] == 'counted'
    assert saved['counted_at'].endswith('+00:00')
    assert saved['published_at'] is None


def test_result_persists_across_connections(tmp_path, result):
    path = tmp_path / 'results.db'
    save_count(result, path)
    assert get_count('DEMO-001', path)['winner_id'] == 'CAND-A'


def test_missing_result_returns_none(tmp_path):
    assert get_count('missing', tmp_path / 'new.db') is None


def test_duplicate_election_cannot_overwrite_saved_count(tmp_path, result):
    path = tmp_path / 'results.db'
    save_count(result, path)
    changed = copy.deepcopy(result)
    changed['winner_id'] = 'CAND-B'
    with pytest.raises(ResultStorageError, match='already exists'):
        save_count(changed, path)
    assert get_count('DEMO-001', path)['winner_id'] == 'CAND-A'


@pytest.mark.parametrize('field,value', [
    ('election_id', ''),
    ('winner_id', None),
    ('total_ballots', -1),
    ('total_ballots', True),
    ('rounds', []),
])
def test_invalid_result_rejected(tmp_path, result, field, value):
    result[field] = value
    with pytest.raises(ResultStorageError):
        save_count(result, tmp_path / 'bad.db')


def test_database_has_no_voter_identity_fields(tmp_path, result):
    path = tmp_path / 'results.db'
    save_count(result, path)
    with sqlite3.connect(path) as con:
        cols = {row[1] for row in con.execute('PRAGMA table_info(election_results)')}
    assert 'voter_id' not in cols
    assert 'voter_name' not in cols
    assert 'ballot_id' not in cols
