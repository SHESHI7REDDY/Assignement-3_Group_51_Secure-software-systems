"""Subprocess checks of launcher isolation and the real combined voting flow."""
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def demo(tmp_path):
    for name in ('app', 'scripts', 'frontend'):
        shutil.copytree(ROOT / name, tmp_path / name,
                        ignore=shutil.ignore_patterns('__pycache__'))
    # Existing project data must not be consumed or changed by the launcher.
    (tmp_path / 'data').mkdir()
    sentinel = tmp_path / 'data' / 'existing-election.txt'
    sentinel.write_text('Preserve the completed election')
    return tmp_path


def prepare(demo):
    subprocess.run([sys.executable, '-m', 'scripts.demo_runtime', '--prepare-only'],
                   cwd=demo, check=True, capture_output=True, text=True, timeout=60)


def test_launcher_preserves_isolated_state_and_private_keys(demo):
    prepare(demo)
    data = demo / '.demo-data'
    config = (data / 'private-config.json').read_bytes()
    with sqlite3.connect(data / 'candidates.db') as connection:
        connection.execute("UPDATE candidates SET name='Edited name', active=0 WHERE candidate_id='DEMO-C004'")
        connection.execute("UPDATE elections SET status='CLOSED'")
    prepare(demo)
    assert (data / 'private-config.json').read_bytes() == config
    assert (demo / 'data' / 'existing-election.txt').read_text() == 'Preserve the completed election'
    assert not (demo / 'data' / 'auth_users.db').exists()
    with sqlite3.connect(data / 'candidates.db') as connection:
        assert connection.execute('SELECT status FROM elections').fetchone()[0] == 'CLOSED'
        assert connection.execute("SELECT name,active FROM candidates WHERE candidate_id='DEMO-C004'").fetchone() == ('Edited name', 0)
    if os.name != 'nt':
        assert (data / 'private-config.json').stat().st_mode & 0o077 == 0


def test_launcher_refuses_to_replace_missing_settings(demo):
    prepare(demo)
    (demo / '.demo-data' / 'private-config.json').unlink()
    result = subprocess.run([sys.executable, '-m', 'scripts.demo_runtime', '--prepare-only'],
                            cwd=demo, capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert 'keys will not be replaced' in result.stderr
    assert not (demo / '.demo-data' / 'private-config.json').exists()


def test_launcher_real_auth_candidate_ballot_and_results_flow(demo):
    # Use the launcher's fixed loopback port, matching both verifier settings.
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', 8000))
        except OSError:
            pytest.skip('Launcher integration test requires unused port 8000')
    env = {**os.environ, 'BROWSER': 'true'}
    # Prevent opening desktop apps during automated verification.
    runner = ('import sys; from scripts import demo_runtime as d; '
              'd.webbrowser.open=lambda *a: None; d.open_accounts=lambda *a: None; d.main()')
    process = subprocess.Popen([sys.executable, '-u', '-c', runner], cwd=demo,
                               env=env, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, text=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path, body=None, token=None, method=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request('http://127.0.0.1:8000' + path,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers=headers, method=method)
        try:
            response = opener.open(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def state(expected):
        for _ in range(100):
            if request('/ballots/candidates')[1]['status'] == expected:
                return
            time.sleep(.1)
        pytest.fail('Election did not reach ' + expected)

    try:
        for _ in range(200):
            if process.poll() is not None:
                pytest.fail('Launcher stopped before becoming ready: ' + process.stderr.read())
            try:
                if request('/health')[0] == 200:
                    break
            except OSError:
                time.sleep(.1)
        else:
            pytest.fail('Launcher readiness timed out')
        config = json.loads((demo / '.demo-data' / 'private-config.json').read_text())
        tokens = {}
        for username in ('demo_voter', 'demo_officer', 'demo_admin', 'demo_ineligible'):
            code, response = request('/auth/login', {'username': username, 'password': config['passwords'][username]})
            assert code == 200
            tokens[username] = response['access_token']
        election = 'DEMO-A3-ELECTIONS'
        payload = {'election_id': election, 'name': 'Extra candidate', 'party': 'Independent', 'ballot_order': 10}
        assert request('/candidates', payload)[0] == 401
        assert request('/candidates', payload, tokens['demo_voter'])[0] == 403
        code, candidate = request('/candidates', payload, tokens['demo_officer'])
        assert code == 201
        path = '/candidates/' + candidate['candidate_id']
        assert request(path + '?election_id=' + election, {'name': 'Edited extra'}, tokens['demo_officer'], 'PATCH')[0] == 200
        assert request(path + '/deactivate?election_id=' + election, {}, tokens['demo_officer'])[0] == 200
        decision = request('/eligibility/check', {'voter_id': 'V0002'}, tokens['demo_ineligible'])
        assert decision[0] == 200 and decision[1]['eligible'] is False
        process.stdin.write('2\n')
        process.stdin.flush()
        state('OPEN')
        ballot = {'election_id': election, 'preferences': [
            {'candidate_id': f'DEMO-C00{i}', 'rank': i} for i in range(1, 5)]}
        assert request('/ballots/submit', ballot, tokens['demo_voter'])[0] == 200
        assert request('/ballots/submit', ballot, tokens['demo_voter'])[0] == 409
        assert request('/candidates', payload, tokens['demo_officer'])[0] == 409
        process.stdin.write('3\n')
        process.stdin.flush()
        state('CLOSED')
        assert request('/results/count', {}, tokens['demo_voter'])[0] == 403
        assert request('/results/count', {}, tokens['demo_admin'])[0] == 201
        assert request('/results/' + election + '/publish', {}, tokens['demo_admin'])[0] == 200
        assert request('/results/' + election)[0] == 200
        process.stdin.write('5\n')
        process.stdin.flush()
        assert process.wait(timeout=15) == 0
    finally:
        if process.poll() is None:
            process.send_signal(__import__('signal').SIGINT)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        process.stdin.close()
        process.stderr.close()
