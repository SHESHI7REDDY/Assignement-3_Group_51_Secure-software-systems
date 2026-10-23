# Draft interface contracts
Status: discussion draft. Paths are wired; all feature operations return 501.
Request/response models are intentionally not fixed until the owners agree them.

| Owner | Draft endpoints |
| --- | --- |
| Varshil | POST /auth/register, /auth/login, /auth/logout; GET /auth/verify |
| Ved | POST /eligibility/enrol, /eligibility/check, /eligibility/authorizations, /eligibility/authorizations/redeem (service); GET /eligibility/status/{voter_id}; see app/eligibility/README.md |
| Akshit | GET /ballots/template; POST /ballots |
| Sashi | GET /candidates; POST /candidates; PATCH /candidates/{candidate_id} |
| Moinul | POST /results/count; GET /results/{election_id}; POST /results/{election_id}/publish; GET /results/{election_id}/audit |

Agree before implementing:
- Opaque IDs and election_id; explicit request/response schemas; UTC timestamps.
- A trusted server-side authentication dependency; do not trust role/user headers.
- Each endpoint's permissions, status codes and error payloads.
- Election-scoped candidate IDs and frozen candidate lists when voting starts.
- Eligibility authorization, one-time consumption, concurrent submissions and retries.
- Recovery if eligibility changes but ballot persistence fails; test the combined workflow.
- No voter_id, name or identity token stored beside anonymous ballot preferences.
- Logs and authorization records must not leak the voter-to-ballot association.
- Database table ownership, schema creation and fixtures for each module.
- Encryption key storage and tally access; no custom cryptographic schemes.
- Read/publication rules and audit integrity verification.

Suggested error meanings after implementation: 401 unauthenticated, 403 forbidden,
409 state conflict, 422 validation failure. Validate and document exact behavior.
Local mocks belong in explicit development/test fixtures and must not bypass integrated security.
The skeleton has no mock login or permissive authorization dependency.
