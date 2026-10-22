import pytest

from app.candidates.repository import (
    CandidateConflictError,
    ElectionLockedError,
    ElectionNotFoundError,
    create_candidate,
    get_connection,
    init_db,
    list_candidates,
)
from app.candidates.schemas import CandidateCreate


@pytest.fixture
def database(tmp_path):
    db_path = tmp_path / "creation.db"
    init_db(db_path)

    connection = get_connection(db_path)
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO elections (election_id, title)
                VALUES (?, ?)
                """,
                ("TEST-CREATE", "Fictional creation test"),
            )
    finally:
        connection.close()

    return db_path


def candidate_data(**changes):
    payload = {
        "election_id": "TEST-CREATE",
        "name": "Sashi",
        "party": "Independent",
        "ballot_order": 1,
    }
    payload.update(changes)
    return CandidateCreate(**payload)


def test_valid_candidate_is_created(database):
    result = create_candidate(candidate_data(), database)

    assert result["candidate_id"].startswith("CAND-")
    assert result["name"] == "Sashi"
    assert result["election_id"] == "TEST-CREATE"
    assert result["active"] == 1

    stored = list_candidates("TEST-CREATE", database)
    assert len(stored) == 1
    assert stored[0]["candidate_id"] == result["candidate_id"]


def test_duplicate_position_does_not_insert_second_candidate(database):
    create_candidate(candidate_data(), database)

    with pytest.raises(CandidateConflictError):
        create_candidate(
            candidate_data(name="Ved", ballot_order=1),
            database,
        )

    assert len(list_candidates("TEST-CREATE", database)) == 1


def test_different_positions_are_accepted(database):
    first = create_candidate(candidate_data(), database)
    second = create_candidate(
        candidate_data(name="Ved", ballot_order=2),
        database,
    )

    assert first["candidate_id"] != second["candidate_id"]
    assert len(list_candidates("TEST-CREATE", database)) == 2


def test_unknown_election_does_not_insert_candidate(database):
    with pytest.raises(ElectionNotFoundError):
        create_candidate(
            candidate_data(election_id="MISSING"),
            database,
        )

    assert list_candidates("TEST-CREATE", database) == []


@pytest.mark.parametrize("status", ["OPEN", "CLOSED"])
def test_non_draft_election_rejects_creation(database, status):
    connection = get_connection(database)
    try:
        with connection:
            connection.execute(
                "UPDATE elections SET status = ? WHERE election_id = ?",
                (status, "TEST-CREATE"),
            )
    finally:
        connection.close()

    with pytest.raises(ElectionLockedError):
        create_candidate(candidate_data(), database)

    assert list_candidates("TEST-CREATE", database) == []


def test_sql_like_name_is_stored_as_data(database):
    submitted_name = "O'Brien'); DROP TABLE candidates; --"

    result = create_candidate(
        candidate_data(name=submitted_name),
        database,
    )

    assert result["name"] == submitted_name

    stored = list_candidates("TEST-CREATE", database)
    assert len(stored) == 1
    assert stored[0]["name"] == submitted_name