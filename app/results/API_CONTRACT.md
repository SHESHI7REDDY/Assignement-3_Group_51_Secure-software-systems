> Historical fixture API notes. The shared and standalone server entry points now use real login and accepted ballots. See [results integration](../../docs/results-integration.md) for the current setup and endpoints. These fixture routes remain only in isolated module tests.

﻿# Results & Audit Module — API Contract

## 1. Module Overview

**Module owner:** Moinul Alam

**Module:** Counting, Results & Audit

**Assigned requirements:** RES-01, RES-02, RES-03, RES-04

Describe the module's responsibility for election counting, results publication and audit integrity.

## 2. Shared Data Fields

| Field | Data Type | Description |
|---|---|---|
| election_id | String | TODO |
| ballot_id | String | TODO |
| candidate_id | String | TODO |
| preferences | List of strings | TODO |
| status | String | TODO |
| rounds | List | TODO |
| winner_id | String or null | TODO |
| published_at | UTC timestamp or null | TODO |

## 3. REST API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /results/count | TODO |
| GET | /results/{election_id} | TODO |
| POST | /results/{election_id}/publish | TODO |
| GET | /results/{election_id}/audit | TODO |

## 4. Integration Assumptions

- Candidate data source: TODO
- Anonymous ballot data source: TODO
- Authorization mechanism: TODO
- Shared election identifier format: TODO

## 5. Security Boundaries

### RES-01 — Preferential Counting

Explain the anonymous ballot input and counting rules.

### RES-02 — Audit Integrity

Explain the chosen integrity mechanism and its limitations.

### RES-03 — Secure Publication

Explain how authorized administrators are distinguished from ordinary users.

### RES-04 — Published Results API

Explain which result information should be publicly accessible and when.

## 6. Verification Plan

| Requirement | Test Scenario | Expected Outcome |
|---|---|---|
| RES-01 | Count a known fictional election | Correct winner and counting rounds |
| RES-02 | Modify an existing audit event | Integrity verification fails |
| RES-03 | Attempt publication as a voter | HTTP 403 |
| RES-04 | Request an unpublished result | Result is not disclosed |

