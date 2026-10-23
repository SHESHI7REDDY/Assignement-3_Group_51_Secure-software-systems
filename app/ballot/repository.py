"""Ballots share the eligibility transaction, but have no voter/account columns.

The earlier standalone data/ballots.db is not imported or reset. Its mock
ballots are not evidence of votes cast through the integrated application.
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS accepted_ballots (
    ballot_id TEXT PRIMARY KEY,
    election_id TEXT NOT NULL,
    encrypted_ballot TEXT NOT NULL
);
"""


def initialise_database(connection):
    connection.execute(SCHEMA)


def save_ballot(connection, election_id, encrypted_ballot, ballot_id):
    # Commit belongs to the caller, together with the one-vote flag.
    connection.execute(
        "INSERT INTO accepted_ballots VALUES (?, ?, ?)",
        (ballot_id, election_id, encrypted_ballot),
    )
