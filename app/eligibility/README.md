# Voter eligibility and one-vote rule
Owner: Ved · Branch: `feature/eligibility` · Requirements: ELIG-01 to ELIG-04

Status: eligibility rules and access checks have module tests. Real account identity is connected; ballot submission integration remains pending.

| File | Purpose |
| --- | --- |
| `router.py` | REST endpoints under `/eligibility` |
| `schemas.py` | Strict Pydantic request models (ELIG-03) |
| `service.py` | Eligibility rule engine (ELIG-01), atomic one-vote rule (ELIG-02) |
| `security.py` | Token verification, roles, IDOR check, pseudonyms (ELIG-03/04) |
| `audit.py` | SHA-256 hash-chained audit log (ELIG-04) |
| `repository.py` | SQLite schema + fictional seed data |
| `config.py` | Settings from environment variables only |
| `standalone.py` | Standalone server including real authentication |

## Run standalone with real authentication
```bash
export ELECTION_ID=DEMO-A3-ELECTIONS
python -m scripts.prepare_demo_roll                        # preserve existing voter and vote records
python -m uvicorn app.eligibility.standalone:app --reload --port 8002
```
Open http://127.0.0.1:8002/ (GUI) and http://127.0.0.1:8002/docs.
The standalone server now includes `/auth/login`, `/auth/verify` and `/auth/logout`.
Use a registered account with a trusted voter link. The GUI no longer accepts
caller-selected roles or voter identities. Mock authentication is disabled by
default; the standalone mock endpoint is for explicitly enabled API test setups
only. The shared app (`app/main.py`) never exposes `/dev/mock-token`.

## Test
```bash
python -m pytest tests/eligibility -q
bandit -r app/eligibility -ll
```

## Endpoints
| Method and path | Roles | Purpose |
| --- | --- | --- |
| `POST /eligibility/check` | voter (self), officer | `{eligible, reason}` |
| `POST /eligibility/authorizations` | voter (self, ONLINE), officer | Atomically mark voted + issue one-time ballot token |
| `POST /eligibility/authorizations/redeem` | service | Ballot module redeems token once; returns division |
| `POST /eligibility/enrol` | voter (self → PENDING), officer (→ ENROLLED) | Enrol |
| `GET /eligibility/status/{voter_id}` | voter (self), officer | Enrolment status |
| `POST /eligibility/enrolments/{voter_id}/approve` | officer | Approve self-enrolment |
| `PATCH /eligibility/electors/{voter_id}/address` | voter (self), officer | Update address |
| `GET /eligibility/audit/verify`, `/audit/recent` | officer | Audit hash-chain check |

401 bad/missing token · 403 wrong role, other voter or ineligible · 409 already voted / token used · 422 invalid input.

## Integration contract
- **Auth (Varshil):** set `ELIG_AUTH_VERIFY_URL` to `/auth/verify`. It must accept `Authorization: Bearer <token>`
  and return `{"user_id", "role", "voter_id"}` with role `voter`, `officer` or `service`.
- **Ballot (Akshit):** call `POST /eligibility/authorizations/redeem` with a `service` token and
  `{"ballot_token": "..."}` before storing a ballot. Store only the returned `division`, never a voter ID.

## Seed voters (fictional)
V0001 eligible · V0002 under 18 · V0003 not a citizen · V0004 disqualified · V0005 pending ·
V0006 already voted · V0007 eligible (race test) · V0008 turns 18 on election day.

## Assumptions
A voter is marked as voted when the ballot token is issued (as a paper roll is marked when the ballot is handed over).
Settings come from environment variables; without secrets set, random per-process development values are used.

## Shared application GUI

Start the shared app on port 8000 with the verified identity configuration:

```bash
export ELECTION_ID=DEMO-A3-ELECTIONS
export ELIG_MOCK_AUTH=0
export ELIG_AUTH_VERIFY_URL=http://127.0.0.1:8000/auth/verify
python -m uvicorn app.main:app --reload --port 8000
```

Open `/static/eligibility/index.html`. Sign in with the registered account.
For a voter, the linked voter ID is filled from the verified identity and cannot
be edited in the normal interface. The server still enforces ownership.
Tokens remain in page memory, passwords are cleared after login attempts, and
logout revokes the page's session. A refresh requires sign-in again.

The GUI supports enrolment status, eligibility checks, enrolment and address
updates. Officer approval and audit controls are shown only to an officer.
Hiding controls is a usability feature; server checks provide access control.
Ballot-token issuance is deliberately not exposed by this intermediate GUI:
checking eligibility must not mark the voter as voted before the ballot workflow
is connected. Backend authorisation and redemption APIs remain available for
the reviewed ballot integration and their existing tests.
