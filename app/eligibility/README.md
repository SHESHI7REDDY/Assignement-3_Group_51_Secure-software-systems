# Voter eligibility and one-vote rule
Owner: Ved · Branch: `feature/eligibility` · Requirements: ELIG-01 to ELIG-04

Status: implemented (ELIG-01 to ELIG-04 fully implemented, 45 security tests).

| File | Purpose |
| --- | --- |
| `router.py` | REST endpoints under `/eligibility` |
| `schemas.py` | Strict Pydantic request models (ELIG-03) |
| `service.py` | Eligibility rule engine (ELIG-01), atomic one-vote rule (ELIG-02) |
| `security.py` | Token verification, roles, IDOR check, pseudonyms (ELIG-03/04) |
| `audit.py` | SHA-256 hash-chained audit log (ELIG-04) |
| `repository.py` | SQLite schema + fictional seed data |
| `config.py` | Settings from environment variables only |
| `standalone.py` | Standalone demo with development mock login |

## Run standalone (demo without the Auth module)
```bash
python -m app.eligibility.repository                       # seed 8 fictional voters into data/eligibility.db
python -m uvicorn app.eligibility.standalone:app --reload --port 8002
```
Open http://127.0.0.1:8002/ (GUI) and http://127.0.0.1:8002/docs.
Only the standalone app exposes `POST /dev/mock-token`. The shared app (`app/main.py`) does not.

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
