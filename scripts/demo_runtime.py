"""Trusted local demo operator. No public role-grant or lifecycle routes."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '.demo-data'
URL = 'http://127.0.0.1:8000'
ELECTION = 'DEMO-A3-ELECTIONS'
ACCOUNTS = (
    ('demo_voter', 'voter', 'V0001'),
    ('demo_officer', 'officer', None),
    ('demo_admin', 'admin', None),
    ('demo_ineligible', 'voter', 'V0002'),
)


def write_private(path, content):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as destination:
        destination.write(content)


def configure():
    DATA.mkdir(mode=0o700, exist_ok=True)
    config_path = DATA / 'private-config.json'
    if not config_path.exists():
        if any(DATA.glob('*.db')) or any(DATA.glob('*.sqlite3')):
            raise RuntimeError('Demo databases exist but their private settings are missing. Restore the settings backup; keys will not be replaced.')
        from cryptography.fernet import Fernet
        config = {
            'ELIG_AUTH_SECRET': secrets.token_hex(32),
            'ELIG_PSEUDONYM_KEY': secrets.token_hex(32),
            'RESULTS_AUDIT_HMAC_KEY': secrets.token_hex(32),
            'AUTH_MFA_KEY': Fernet.generate_key().decode('ascii'),
            'passwords': {name: 'Demo9_' + secrets.token_urlsafe(18) for name, _, _ in ACCOUNTS},
        }
        write_private(config_path, json.dumps(config))
    config = json.loads(config_path.read_text(encoding='utf-8'))
    for key in ('ELIG_AUTH_SECRET', 'ELIG_PSEUDONYM_KEY', 'RESULTS_AUDIT_HMAC_KEY', 'AUTH_MFA_KEY'):
        os.environ[key] = config[key]
    os.environ.update({
        'VOTING_DATA_DIR': str(DATA),
        'ELIG_DB_PATH': str(DATA / 'eligibility.db'),
        'RESULTS_DB_PATH': str(DATA / 'platform_results.sqlite3'),
        'BALLOT_KEY_FILE': str(DATA / 'ballot_key.key'),
        'ELECTION_ID': ELECTION,
        'ELECTION_DATE': '2026-12-05',
        'ELIG_MOCK_AUTH': '0',
        'ELIG_AUTH_VERIFY_URL': URL + '/auth/verify',
        'CAND_AUTH_VERIFY_URL': URL + '/auth/verify',
    })
    return config


def prepare(config):
    # Imports occur after configuration so all modules use the isolated directory.
    from app.auth import repository
    from app.auth.profiles import initialise_profiles, link_demo_voter
    from app.auth.schemas import RegisterRequest
    from app.auth.service import register_user, verify_password
    from app.candidates.repository import get_connection, init_db
    from app.candidates.seed import seed_demo
    from scripts.prepare_demo_roll import main as prepare_roll

    initialise_profiles()
    for name, role, voter_id in ACCOUNTS:
        password = config['passwords'][name]
        user = repository.get_user_by_username(name)
        if user is None:
            register_user(RegisterRequest(username=name, password=password))
            user = repository.get_user_by_username(name)
        if not verify_password(password, user['password_hash']):
            raise RuntimeError(f'Demo account {name} was changed. Restore its private configuration; existing passwords will not be overwritten.')
        with closing(repository.get_connection()) as connection:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                link = connection.execute('SELECT voter_id FROM account_voters WHERE user_id=?', (user['id'],)).fetchone()
                if role != 'voter' and link:
                    raise RuntimeError('A privileged demo account is already linked as a voter.')
                if user['role'] not in ('voter', role):
                    raise RuntimeError('A demo account has an unexpected role.')
                if user['role'] != role:
                    connection.execute('UPDATE users SET role=? WHERE id=?', (role, user['id']))
                    connection.execute('UPDATE auth_sessions SET revoked=1 WHERE user_id=?', (user['id'],))
                if role == 'officer':
                    connection.execute('INSERT OR IGNORE INTO officer_elections(user_id,election_id) VALUES (?,?)', (user['id'], ELECTION))
        if voter_id:
            link_demo_voter(name, voter_id)
    prepare_roll()
    init_db()
    with closing(get_connection()) as connection:
        exists = connection.execute('SELECT status FROM elections WHERE election_id=?', (ELECTION,)).fetchone()
    # Never reseed an existing election: preserve edited names, deactivations and state.
    if exists is None:
        seed_demo()
    credentials = DATA / 'DEMO-ACCOUNTS.txt'
    content = 'PRIVATE LOCAL DEMO ACCOUNTS - do not submit or share this file\n\n'
    content += 'Election: ' + ELECTION + '\nWebsite: ' + URL + '\n\n'
    for name, role, voter_id in ACCOUNTS:
        content += f'Username: {name}\nPassword: {config["passwords"][name]}\nRole: {role}'
        content += f'\nVoter ID: {voter_id}\n\n' if voter_id else '\n\n'
    content += 'Use demo_officer for candidate and eligibility management.\nUse demo_admin for counting and publishing after closing the election.\nUse demo_ineligible to demonstrate rejection of an underage voter.\n'
    if not credentials.exists():
        write_private(credentials, content)
    return credentials


def open_accounts(path):
    if sys.platform == 'darwin':
        subprocess.Popen(['open', str(path)])
    elif os.name == 'nt':
        os.startfile(path)
    else:
        print(f'Open your private account file: {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true', help='Prepare isolated data without starting a server.')
    args = parser.parse_args()
    # Fail before touching data when another server owns our verifier port.
    if not args.prepare_only:
        try:
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 8000))
        except OSError:
            raise RuntimeError('Port 8000 is already in use. Stop the previous server in its terminal and launch again.') from None
    config = configure()
    credentials = prepare(config)
    print(f'Private demo accounts: {credentials}')
    if args.prepare_only:
        return
    from app.ballot.lifecycle import transition
    from app.candidates.repository import get_connection
    log_path = DATA / 'server.log'
    with log_path.open('a', encoding='utf-8') as log:
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError(f'Server could not start. See {log_path}')
                try:
                    with opener.open(URL + '/health', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.2)
            else:
                raise RuntimeError(f'Server did not become ready. See {log_path}')
            webbrowser.open(URL)
            open_accounts(credentials)
            print('\nThe application is ready. Keep this window open.')
            while True:
                with closing(get_connection()) as connection:
                    state = connection.execute('SELECT status FROM elections WHERE election_id=?', (ELECTION,)).fetchone()['status']
                print(f'\nDemo election: {state}')
                print('1 Open website  |  2 Open election for voting  |  3 Close election for results')
                print('4 Open private account details  |  5 Stop application')
                try:
                    choice = input('Choose 1-5: ').strip()
                except EOFError:
                    break
                if choice == '1':
                    webbrowser.open(URL)
                elif choice in ('2', '3'):
                    try:
                        transition(ELECTION, 'OPEN' if choice == '2' else 'CLOSED')
                        print('Election state updated. Refresh the web page.')
                    except ValueError as error:
                        print(f'Cannot change election: {error}')
                elif choice == '4':
                    open_accounts(credentials)
                elif choice == '5':
                    break
        finally:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
            print('Application stopped. Demo data and private keys were preserved.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nDemo stopped.')
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print(f'Demo could not start: {error}', file=sys.stderr)
        raise SystemExit(1)
