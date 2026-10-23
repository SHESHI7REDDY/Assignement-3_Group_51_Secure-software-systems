# Ballot Casting and Privacy Module

This module implements the Ballot Casting and Privacy functionality for the Electronic Voting Platform.

## Implemented Security Requirements

### BAL-01 – Preferential Ballot Validation
The system validates House of Representatives candidate rankings and rejects:

- duplicate preference ranks
- missing preferences
- duplicate candidates
- invalid candidate identifiers

### BAL-02 – Authorised Ballot Submission
Ballot submission requires:

- a valid authentication token
- the `voter` role

Unauthorised requests are rejected with HTTP 401 or HTTP 403 responses.

### BAL-03 – Encrypted Ballot Storage
Ballot preferences are encrypted using Fernet encryption before they are saved to the SQLite database.

The encryption key is stored separately and excluded from Git.

### BAL-04 – Anonymous Ballot Storage
Stored ballots do not contain:

- voter ID
- voter name
- username
- email address
- authentication token

This keeps voter identity separate from voting preferences.

## Module Structure

```text
app/ballot/
├── __init__.py
├── repository.py
├── router.py
├── schemas.py
├── service.py
└── standalone.py