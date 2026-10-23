# Ballot module

Owner: Akshit.

The active combined application imports `app.ballot`, not the historical
standalone demonstration in the top-level `ballot/` folder.

The module validates preferential rankings, verifies the real logged-in voter,
checks the election state and eligibility, and stores an encrypted accepted ballot.
The integrated submission transaction also consumes the voting authorisation and
updates the voting record. A failed write rolls the transaction back.

| Area | Main files |
| --- | --- |
| HTTP routes | `router.py` |
| Shared identity, candidate and submission integration | `integration.py` |
| Trusted local election transitions | `lifecycle.py` |

See the [integration guide](../../docs/ballot-integration.md) and
[combined API summary](../../docs/api-contracts.md). Run the full test suite from
the repository root using `python -m pytest -q`.

The election moves from DRAFT to OPEN to CLOSED. Candidate management is limited
to DRAFT and ballot submission to OPEN. The local lifecycle command cannot reopen
a CLOSED election.

Accepted ballot rows omit voter and account identity fields. This is basic
storage separation; it does not establish cryptographic unlinkability against
an operator who can inspect the databases, logs or timing information.
Keep the persistent encryption key private and backed up. Losing or replacing
it can make existing ballots unreadable.
