import sqlite3

import pytest

from app.candidates.repository import get_connection, init_db


@pytest.fixture
def database(tmp_path):
    """Use a separate temporary database for each test."""
    db_path = tmp_path / "candidates.db"
    init_db(db_path)
    connection = get_connection(db_path)

    with connection:
        connection.execute(
            """
            INSERT INTO elections (election_id, title)
            VALUES (?, ?)
            """,
            ("ELECTION-2026", "Fictional demonstration election"),
        )

    try:
        yield connection, db_path
    finally:
        connection.close()


def insert_candidate(
    connection,
    candidate_id="CAND-001",
    election_id="ELECTION-2026",
    name="Alex O'Brien",
    ballot_order=1,
):
    with connection:
        connection.execute(
            """
            INSERT INTO candidates (
                candidate_id, election_id, name, party, ballot_order
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                election_id,
                name,
                "Independent",
                ballot_order,
            ),
        )


def test_valid_candidate_is_stored(database):
    connection, _ = database
    insert_candidate(connection)

    row = connection.execute(
        "SELECT name, active FROM candidates WHERE candidate_id = ?",
        ("CAND-001",),
    ).fetchone()

    assert row["name"] == "Alex O'Brien"
    assert row["active"] == 1


def test_unknown_election_is_rejected(database):
    connection, _ = database

    with pytest.raises(sqlite3.IntegrityError):
        insert_candidate(connection, election_id="UNKNOWN")


def test_duplicate_ballot_order_is_rejected(database):
    connection, _ = database
    insert_candidate(connection)

    with pytest.raises(sqlite3.IntegrityError):
        insert_candidate(
            connection,
            candidate_id="CAND-002",
            name="Jordan Example",
            ballot_order=1,
        )

    count = connection.execute(
        "SELECT COUNT(*) FROM candidates"
    ).fetchone()[0]

    assert count == 1


@pytest.mark.parametrize("name", ["", "   ", "A" * 121])
def test_invalid_name_is_rejected_by_database(database, name):
    connection, _ = database

    with pytest.raises(sqlite3.IntegrityError):
        insert_candidate(connection, name=name)


@pytest.mark.parametrize("ballot_order", [0, 1001, "invalid"])
def test_invalid_ballot_order_is_rejected(database, ballot_order):
    connection, _ = database

    with pytest.raises(sqlite3.IntegrityError):
        insert_candidate(connection, ballot_order=ballot_order)


def test_initialisation_preserves_existing_records(database):
    connection, db_path = database
    insert_candidate(connection)

    init_db(db_path)

    count = connection.execute(
        "SELECT COUNT(*) FROM candidates"
    ).fetchone()[0]

    assert count == 1