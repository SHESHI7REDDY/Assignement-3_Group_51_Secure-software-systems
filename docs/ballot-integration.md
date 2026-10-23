# Ballot integration

This change joins authentication, eligibility, candidate selection and ballot storage. Results counting and publishing still need a separate integration change. Passing these tests does not mean the whole assignment is finished.

## How it works

1. The voter logs in through the real authentication service.
2. The server reads the account's voter link from the authentication database. Request fields and demonstration headers cannot set the voter's identity or role.
3. The ballot page loads the configured election and its active candidates from the candidate database.
4. Submission checks that the election is OPEN and every active candidate has a different rank from 1 to the number of candidates.
5. The server checks eligibility again. In one SQLite transaction it marks the voter as voted, issues and redeems a one-use token, appends the eligibility audit records and stores the encrypted ballot.
6. If any of those steps fail, the transaction rolls back. A duplicate submission returns ALREADY_VOTED and creates no extra ballot.

The new `accepted_ballots` table is in the eligibility database. Its columns are `ballot_id`, `election_id` and `encrypted_ballot`. It has no voter ID, username, account ID or token. Keeping these tables in one database allows the one-vote flag and ballot to commit together. This prototype does not provide cryptographic anonymity against the database operator: transaction timing and access to the databases could still reveal relationships. It is not an end-to-end verifiable election system.

The earlier `data/ballots.db` is left untouched. Its old demonstration ballots are not imported into the new voting flow. Do not delete files or databases while the server is running.

## Local run

Use Python 3.12 and the `.venv-integration` environment. Keep using the integration branch until all modules have been checked.

Before opening the election, finish candidate creation, editing and deactivation demonstrations. Candidate changes are allowed only while the election is DRAFT. Do not change the status back to DRAFT to repeat a demonstration.

In the project terminal:

```sh
source .venv-integration/bin/activate
export ELECTION_ID=DEMO-A3-ELECTIONS
export ELIG_MOCK_AUTH=0
export ELIG_AUTH_VERIFY_URL=http://127.0.0.1:8000/auth/verify
export CAND_AUTH_VERIFY_URL=http://127.0.0.1:8000/auth/verify
python -m scripts.prepare_demo_roll
```

Keep the existing voter account and voter link. The roll preparation command preserves voting records. Only if the candidate database has not been prepared, and the election is still DRAFT, run `python -m app.candidates.seed`.

Generate and keep stable `ELIG_AUTH_SECRET` and `ELIG_PSEUDONYM_KEY` values in your local server environment before the final recording. These are two separate random secrets. Do not commit or share them. The app does not automatically load `.env`; exported values must be present in the terminal that starts the server. Missing values currently generate development warnings and change when the process restarts.

When candidate management tests are finished, the trusted local operator can open the fictional election:

```sh
python -m app.ballot.lifecycle DEMO-A3-ELECTIONS OPEN
python -m uvicorn app.main:app --reload --port 8000
```

The local command requires access to the server database files. It is not a public election-management API. Supported transitions are DRAFT to OPEN and OPEN to CLOSED. Repeating the current state is safe. CLOSED cannot be reopened.

Open `http://127.0.0.1:8000/static/ballot/index.html`. Log in with the existing linked voter account. The page keeps the token in memory and requires a separate login from the eligibility page.

Rank every displayed candidate once, confirm the choices and submit. This is a real local prototype vote: successful submission will mark that linked voter as voted for this election. Do not use the same voter for multiple successful demonstrations or reset their voting flag. Use another fictional eligible voter and a separately linked account when another successful vote is needed.

The browser shows an acceptance receipt. The server still rejects a second submission even after refreshing or logging in again. If a network response is lost, check eligibility before retrying: the server may already have committed the vote.

The standalone ballot app also mounts `/static` and includes the real login service. It requires the same configured election, prepared databases and verified account link.

## Verification and report evidence

Run the complete suite with `python -m pytest -q`. The tests use temporary databases and keys; they do not consume a vote in your local demonstration database. Tests cover real login, expired and revoked sessions, rejected mock headers, server-controlled identities, strict request validation, dynamic candidate lists, election state, eligibility checks, concurrent duplicate submissions, rollback, encryption and key loss. The existing eligibility module tests are retained.

Useful screenshots after applying and running this change:

- Full test result on the integration branch.
- Ballot page showing the actual candidate names and election ID.
- Accepted ballot receipt, with no passwords or tokens visible.
- An eligibility check after submission returning ALREADY_VOTED.
- Rejected unauthorised ballot submission in API documentation.

Direct `/eligibility/authorizations` issuance is disabled in real authentication mode. Use `/ballots/submit`, which commits the authorisation and encrypted ballot together. The isolated mock-mode eligibility tests retain their earlier token-issuance contract.

## Work still needed

- Connect results counting to accepted encrypted ballots and the actual candidate list; the existing results fixtures are separate demonstrations.
- Require election closure before counting and publication.
- Complete the officer/admin account and permission setup for management demonstrations.
- Verify the complete browser journey and update the shared home page, report, requirement issues and architecture diagram to match the final implementation.
- Preserve the local ballot encryption key and audit configuration. Losing the ballot key must not cause a new key to be silently created after votes exist.
