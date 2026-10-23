import sqlite3

from fastapi.testclient import TestClient

from app.ballot.standalone import app


client = TestClient(app)

VALID_HEADERS = {
    "x-auth-token": "ballot-demo-token",
    "x-mock-role": "voter",
}

VALID_BALLOT = {
    "election_id": "ELECTION-2026",
    "preferences": [
        {"candidate_id": "CAND-001", "rank": 1},
        {"candidate_id": "CAND-002", "rank": 2},
        {"candidate_id": "CAND-003", "rank": 3},
        {"candidate_id": "CAND-004", "rank": 4},
    ],
}


def test_valid_ballot_is_accepted():
    response = client.post(
        "/ballots/submit",
        json=VALID_BALLOT,
        headers=VALID_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["message"] == \
        "Ballot accepted and securely stored"


def test_duplicate_preferences_are_rejected():
    invalid_ballot = {
        "election_id": "ELECTION-2026",
        "preferences": [
            {"candidate_id": "CAND-001", "rank": 1},
            {"candidate_id": "CAND-002", "rank": 2},
            {"candidate_id": "CAND-003", "rank": 2},
            {"candidate_id": "CAND-004", "rank": 4},
        ],
    }

    response = client.post(
        "/ballots/submit",
        json=invalid_ballot,
        headers=VALID_HEADERS,
    )

    assert response.status_code == 400


def test_unauthorised_ballot_is_rejected():
    response = client.post(
        "/ballots/submit",
        json=VALID_BALLOT,
    )

    assert response.status_code == 401


def test_non_voter_role_is_rejected():
    headers = {
        "x-auth-token": "ballot-demo-token",
        "x-mock-role": "admin",
    }

    response = client.post(
        "/ballots/submit",
        json=VALID_BALLOT,
        headers=headers,
    )

    assert response.status_code == 403


def test_database_does_not_store_voter_identity():
    response = client.post(
        "/ballots/submit",
        json=VALID_BALLOT,
        headers=VALID_HEADERS,
    )

    assert response.status_code == 200

    connection = sqlite3.connect("data/ballots.db")
    cursor = connection.cursor()

    cursor.execute("PRAGMA table_info(ballots)")
    columns = cursor.fetchall()

    connection.close()

    column_names = [column[1] for column in columns]

    assert "voter_id" not in column_names
    assert "voter_name" not in column_names
    assert "email" not in column_names
    assert "username" not in column_names


def test_ballot_is_encrypted_in_database():
    response = client.post(
        "/ballots/submit",
        json=VALID_BALLOT,
        headers=VALID_HEADERS,
    )

    assert response.status_code == 200

    connection = sqlite3.connect("data/ballots.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT encrypted_ballot "
        "FROM ballots "
        "ORDER BY id DESC LIMIT 1"
    )

    encrypted_value = cursor.fetchone()[0]

    connection.close()

    assert "CAND-001" not in encrypted_value
    assert "preferences" not in encrypted_value