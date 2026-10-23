# Combined application API summary

Run `app.main:app` and open `/docs` for the current request and response schemas.
This page describes the integrated application, not the historical fixture APIs.
Protected requests use `Authorization: Bearer <access_token>` from real login.
A role sent by the browser is not trusted.

| Method and path | Access and behaviour |
| --- | --- |
| POST `/auth/register` | Public; creates a voter account |
| POST `/auth/login` | Public; returns a session after valid credentials and required MFA checks |
| GET `/auth/verify` | Valid session; returns the server-verified identity |
| POST `/auth/logout` | Revokes the session |
| GET `/auth/admin/audit` | Administrator |
| POST `/eligibility/enrol` | Linked voter for self, or officer |
| GET `/eligibility/status/{voter_id}` | Self or officer |
| POST `/eligibility/enrolments/{voter_id}/approve` | Officer |
| PATCH `/eligibility/electors/{voter_id}/address` | Self or officer |
| POST `/eligibility/check` | Self or officer; checks the configured election |
| POST `/eligibility/authorizations` | Real-auth mode rejects direct issuance with 409; submit through the ballot API |
| GET `/eligibility/audit/verify` | Officer |
| GET `/eligibility/audit/recent` | Officer |
| GET `/candidates?election_id=...` | Public; lists active candidates |
| POST `/candidates` | Officer assigned to the requested election; DRAFT only |
| PATCH `/candidates/{candidate_id}?election_id=...` | Assigned officer; DRAFT only |
| POST `/candidates/{candidate_id}/deactivate?election_id=...` | Assigned officer; DRAFT only; preserves the record |
| GET `/ballots/candidates` | Returns the configured election and active candidates |
| POST `/ballots/validate` | Linked voter; validates rankings for an OPEN election without recording a vote |
| POST `/ballots/submit` | Linked eligible voter; validates, records the encrypted ballot and consumes voting permission atomically |
| POST `/results/count` | Administrator; configured election must be CLOSED |
| POST `/results/{election_id}/publish` | Administrator; publishes a counted result for the CLOSED configured election |
| GET `/results/{election_id}` | Public; published aggregate result only |
| GET `/results/{election_id}/audit` | Administrator; filtered audit events |
| GET `/results/{election_id}/audit/verify` | Administrator; checks the global results chain |
| GET `/health` | Public; application health, not a security certification |

Candidate creation accepts `election_id`, `name`, `party` and `ballot_order`.
Candidate updates accept editable fields defined in `CandidateUpdate`; use the
query parameter to identify the election. Unknown fields are rejected.

Ballot validation and submission accept:

```json
{
  "election_id": "DEMO-A3-ELECTIONS",
  "preferences": [
    {"candidate_id": "DEMO-C001", "rank": 1},
    {"candidate_id": "DEMO-C002", "rank": 2},
    {"candidate_id": "DEMO-C003", "rank": 3},
    {"candidate_id": "DEMO-C004", "rank": 4}
  ]
}
```

Use the current active candidates rather than assuming the example still matches
the database. Never send a caller-selected voter identity as proof of permission.
Inspect `/docs` and route tests for exact error responses. Typical failures are
401 for missing or invalid authentication, 403 for insufficient permission,
404 for missing records, 409 for state conflicts and 422 for invalid input.

The real submission path coordinates eligibility and ballot storage in one
transaction. Legacy authorisation/redeem routes and mock-auth tests do not replace
that integrated flow. Results fixture routes are not mounted by `app.main`.
