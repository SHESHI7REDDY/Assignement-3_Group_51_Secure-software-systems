# Candidate Management Module

Owner: Sashi

## Purpose

This module provides a candidate directory and protected candidate
management APIs for the electronic voting prototype.

## Implemented functionality

- List active candidates for a selected election in ballot order.
- Create candidates in draft elections.
- Edit candidate names, parties and ballot positions.
- Deactivate candidates while preserving their database records.
- Provide a browser interface for listing and managing candidates.

## Security controls

- Strict request validation with length and range limits.
- Unexpected request fields are rejected.
- Parameterised SQL queries.
- Transactions for candidate changes.
- Candidate changes restricted to draft elections.
- Officer role and election-specific permission checks.
- Bearer tokens verified through a configured authentication service.
- Management requests rejected when identity verification is unavailable.
- Candidate information rendered using textContent.
- Deactivated records retained instead of deleted.

## Run independently

From the project root, activate your virtual environment and install
the project dependencies:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Start the candidate service:

```bash
python -m uvicorn app.candidates.standalone:app --reload --port 8003
```

Candidate webpage:

http://127.0.0.1:8003/static/candidates/index.html

API documentation:

http://127.0.0.1:8003/docs

The demonstration election is DEMO-A3-ELECTIONS.
Demonstration data must be seeded separately; tests use their own data.

## API endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | /candidates?election_id=... | List active candidates |
| POST | /candidates | Create a candidate |
| PATCH | /candidates/{candidate_id}?election_id=... | Edit a candidate |
| POST | /candidates/{candidate_id}/deactivate?election_id=... | Deactivate a candidate |

Management endpoints require an authorised officer identity with
permission for the specified election.

## Authentication integration

The candidate service uses CAND_AUTH_VERIFY_URL to locate the trusted
token-verification endpoint.

The verifier must return an identity compatible with:

```json
{
  "user_id": "officer-001",
  "role": "officer",
  "managed_election_ids": ["DEMO-A3-ELECTIONS"]
}
```

The browser accepts the access token without the Bearer prefix and
adds that prefix to the API request.

Successful management operations through the browser require the
shared authentication service to be running and configured.

## Tests

Run from the project root:

```bash
python -m pytest tests/candidates tests/test_scaffold.py -q
```

The most recently reported result was 85 passing tests, before the
management interface changes.

The tests cover validation, listing, creation, editing, deactivation,
permission checks and rejected operations.

Automated API tests use controlled test identities. These tests do
not execute the browser JavaScript.

## Integration work remaining

- Connect and verify the shared authentication service.
- Agree on shared election identifiers and election-state ownership.
- Verify successful creation, editing and deactivation in the browser.
- Run the integrated application and its full test suite.