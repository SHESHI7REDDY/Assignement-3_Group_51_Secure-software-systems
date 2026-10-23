# Electronic Voting Platform
Secure Software Systems Assignment 3 · Group 51

This educational prototype combines authentication, voter eligibility, candidate
management, ballot submission, counting and result publication in one FastAPI
application. It uses HTML/CSS/JavaScript pages and local SQLite databases.
It is a classroom prototype, not a system for running a real public election.

## Run the application on macOS
Use Python 3.12. From the project folder, create an environment once:

```sh
python3.12 -m venv .venv-integration
source .venv-integration/bin/activate
python -m pip install -r requirements.txt
```

Prepare persistent local settings, then load them in the server terminal:

```sh
python -m scripts.prepare_local_config
source .env.integration
```

The script preserves an existing configuration. The server does not load this
file automatically. Keep this file and `data/ballot_key.key` private and backed up.
Do not replace keys belonging to existing ballots or results.

For a fresh demonstration database, prepare the fictional roll and candidates:

```sh
python -m scripts.prepare_demo_roll
python -m app.candidates.seed
```

The candidate seed requires a DRAFT election. An existing OPEN or CLOSED election
must not be reset for a recording. Use a separate fresh checkout for a new demo.
The default demonstration election is `DEMO-A3-ELECTIONS`.

Start the combined application:

```sh
python -m uvicorn app.main:app --reload --port 8000
```

Open [the home page](http://127.0.0.1:8000/) or
[the API documentation](http://127.0.0.1:8000/docs).
Keep this terminal running. If port 8000 is occupied, stop the previous server
with Ctrl+C in its terminal before starting another instance.

## Accounts and demonstration order
Register accounts through the authentication page linked from the home page.
Public registration creates voters only. Use your own passwords; do not commit
passwords, session tokens, database files or local configuration.

For an existing fictional voter account, link its username to a roll entry:

```sh
python -m app.auth.profiles voter_1 V0001
```

This trusted local command does not grant eligibility or officer permissions.
Officer accounts also need an officer role and an explicit election assignment
in the authentication database, prepared by a trusted local operator.
There is no public officer-registration route. See the
[authentication implementation](docs/varshil_auth_implementation.md) for the
identity and role model. Do not claim officer setup is automatic.

A registered account for the results demonstration can be promoted locally:

```sh
python -m app.auth.demo_admin results_admin
```

This command rejects accounts already linked as voters or assigned as officers.
Log in again after changing a role because previous sessions are revoked.

Demonstrate candidate creation, editing and deactivation while the election is
DRAFT. Then open it from a second terminal using the same environment and settings:

```sh
source .venv-integration/bin/activate
source .env.integration
python -m app.ballot.lifecycle DEMO-A3-ELECTIONS OPEN
```

Log in as an eligible linked voter, check eligibility and submit one ballot.
Confirm that a second submission is rejected. After voting, close the election:

```sh
python -m app.ballot.lifecycle DEMO-A3-ELECTIONS CLOSED
```

Log in as a results administrator, count the accepted ballots and publish the
result. A CLOSED election cannot be reopened. See the
[ballot integration guide](docs/ballot-integration.md) and
[results integration guide](docs/results-integration.md) for details.

## Tests and CI
Run the full suite from the project root:

```sh
python -m pytest -q
```

The reviewed main revision `95a89f1` passed 373 tests. Test totals can change as
work continues; use the result from the exact revision submitted in the report.
Passing tests demonstrate the checked behaviours, not every possible security property.

The GitHub workflow runs the full suite, a Bandit scan of `app/eligibility`, and
a dependency audit against `requirements.txt`. The Bandit scan does not cover
all application modules. See `.github/workflows/eligibility-tests.yml`.

## Team responsibilities
| Member | Main area | Code |
| --- | --- | --- |
| Varshil | Authentication and sessions | `app/auth` |
| Ved | Eligibility and voting authorisations | `app/eligibility` |
| Akshit | Ballot validation and storage | `app/ballot` |
| Shashi | Candidate management | `app/candidates` |
| Moinul | Counting, publication and audit | `app/results` |

The combined entry point is `app/main.py`. The active pages are under `frontend`.
The top-level `ballot/` folder is a historical standalone demonstration; it is
not the ballot module mounted by the combined application.

## Submission documents and limits
See the [requirements register](docs/requirements.md),
[API summary](docs/api-contracts.md) and
[submission checklist](docs/submission-checklist.md).
The report must trace the final approved requirements to code, tests and evidence.

Backend MFA helpers and login checks do not constitute a complete public MFA
enrolment workflow. Keeping identity fields out of accepted ballot rows provides
basic separation, not proof of anonymity against a database operator or timing
analysis. Hash chains also need an independent checkpoint to establish detection
of history truncation or rollback. Describe these limits honestly in the report.
