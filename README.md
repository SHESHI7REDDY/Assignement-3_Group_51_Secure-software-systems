# Electronic Voting Platform
Secure Software Systems Assignment 3 · Group 51

This is the group's shared development skeleton for selected House of Representatives
voting subsystems. It starts a FastAPI server, serves placeholder HTML pages and exposes
draft REST routes. It is not a completed voting system.

## Current status
- Working: application startup, landing page, five module placeholder pages, API docs, health route.
- implemented: authentication, sessions, eligibility, repeat-vote prevention, ballot
  privacy/encryption, candidate security, counting, publication, audit integrity and databases.
- Feature routes deliberately return HTTP 501. They never accept a vote or grant a role.
- Setup checks are not evidence that security requirements have been implemented.
- Selected scope: a local teaching prototype. Senate, overseas access, scanned paper
  ballot ingestion and production scale are outside this starter.

## Run on macOS or Linux
Requires Python 3.10 or newer. Run from the folder containing this README and requirements.txt.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 for the project page, http://127.0.0.1:8000/docs for
interactive API docs and http://127.0.0.1:8000/health for the setup check.
Stop the server with Control+C. The default server binds only to your local machine.

## Run on Windows PowerShell
```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Test the starter
```bash
python -m pytest -q
```
Three scaffold checks cover setup and intentional rejection of unimplemented operations.
Every member must add real security tests for their own requirements.
Dependency ranges are bootstrap constraints; after the group installs and reviews dependencies,
record a tested lock/freeze for reproducible development.

## Ownership
| Member | Branch | Code | Interface | Tests |
| --- | --- | --- | --- | --- |
| Varshil | feature/authentication | app/auth/ | frontend/auth/ | tests/auth/ |
| Ved | feature/eligibility | app/eligibility/ | frontend/eligibility/ | tests/eligibility/ |
| Akshit | feature/ballot | app/ballot/ | frontend/ballot/ | tests/ballot/ |
| Sashi | feature/candidates | app/candidates/ | frontend/candidates/ | tests/candidates/ |
| Moinul | feature/results-audit | app/results/ | frontend/results/ | tests/results/ |

Each module has a standalone entry point; see its README. app/main.py integrates
the same routers. Integrate a thin working election flow early and expand it together.
Every module still needs its own schema, fictional seed data and documented setup.

