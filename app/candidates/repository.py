"""SQLite persistence for candidate management."""

import sqlite3
from pathlib import Path
from uuid import uuid4
from app.candidates.schemas import CandidateCreate, CandidateUpdate
from app.candidates.schemas import CandidateCreate
from app.shared.config import BASE


DEFAULT_DB_PATH = BASE / "data" / "candidates.db"


def get_connection(db_path: Path = DEFAULT_DB_PATH):
    """Open the database with foreign-key enforcement enabled."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_db(db_path: Path = DEFAULT_DB_PATH):
    """Create tables without deleting existing records."""
    connection = get_connection(db_path)

    try:
        with connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS elections (
                    election_id TEXT PRIMARY KEY NOT NULL,
                    title TEXT NOT NULL
                        CHECK(length(trim(title)) BETWEEN 1 AND 200),
                    status TEXT NOT NULL DEFAULT 'DRAFT'
                        CHECK(status IN ('DRAFT', 'OPEN', 'CLOSED'))
                );

                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT PRIMARY KEY NOT NULL,
                    election_id TEXT NOT NULL,
                    name TEXT NOT NULL
                        CHECK(length(trim(name)) BETWEEN 1 AND 120),
                    party TEXT NOT NULL
                        CHECK(length(trim(party)) BETWEEN 1 AND 120),
                    ballot_order INTEGER NOT NULL
                        CHECK(
                            typeof(ballot_order) = 'integer'
                            AND ballot_order BETWEEN 1 AND 1000
                        ),
                    active INTEGER NOT NULL DEFAULT 1
                        CHECK(active IN (0, 1)),
                    FOREIGN KEY (election_id)
                        REFERENCES elections(election_id),
                    UNIQUE(election_id, ballot_order)
                );
                """
            )
    finally:
        connection.close()

def list_candidates(election_id, db_path=DEFAULT_DB_PATH):
    """Return active candidates in ballot order, or None if election is absent."""
    connection = get_connection(db_path)

    try:
        election = connection.execute(
            "SELECT election_id FROM elections WHERE election_id = ?",
            (election_id,),
        ).fetchone()

        if election is None:
            return None

        rows = connection.execute(
            """
            SELECT candidate_id, name, party, ballot_order
            FROM candidates
            WHERE election_id = ? AND active = 1
            ORDER BY ballot_order, candidate_id
            """,
            (election_id,),
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()
class ElectionNotFoundError(Exception):
    """The requested election does not exist."""


class ElectionLockedError(Exception):
    """Candidate changes are prohibited for this election state."""


class CandidateConflictError(Exception):
    """Candidate data conflicts with database constraints."""


def create_candidate(
    candidate: CandidateCreate,
    db_path=DEFAULT_DB_PATH,
):
    """Create a validated candidate in a draft election.

    Authentication must be enforced by the API before calling this function.
    The state check and insertion occur in one write transaction.
    """
    candidate = CandidateCreate.model_validate(candidate)
    connection = get_connection(db_path)

    try:
        with connection:
            # Prevent another writer changing election state between
            # this check and the candidate insertion.
            connection.execute("BEGIN IMMEDIATE")

            election = connection.execute(
                "SELECT status FROM elections WHERE election_id = ?",
                (candidate.election_id,),
            ).fetchone()

            if election is None:
                raise ElectionNotFoundError("Election not found")

            if election["status"] != "DRAFT":
                raise ElectionLockedError(
                    "Candidates can only be added to a draft election"
                )

            candidate_id = f"CAND-{uuid4().hex}"

            connection.execute(
                """
                INSERT INTO candidates (
                    candidate_id,
                    election_id,
                    name,
                    party,
                    ballot_order
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    candidate.election_id,
                    candidate.name,
                    candidate.party,
                    candidate.ballot_order,
                ),
            )

            row = connection.execute(
                """
                SELECT candidate_id, election_id, name,
                       party, ballot_order, active
                FROM candidates
                WHERE candidate_id = ?
                """,
                (candidate_id,),
            ).fetchone()

            return dict(row)

    except sqlite3.IntegrityError as error:
        raise CandidateConflictError(
            "Candidate data conflicts with database constraints"
        ) from error

    finally:
        connection.close()
class CandidateNotFoundError(Exception):
    """Candidate does not exist in the requested election."""


def update_candidate(
    candidate_id,
    election_id,
    changes,
    db_path=DEFAULT_DB_PATH,
):
    changes = CandidateUpdate.model_validate(changes)
    values = changes.model_dump(exclude_unset=True)
    connection = get_connection(db_path)

    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")

            row = connection.execute(
                """
                SELECT c.*, e.status AS election_status
                FROM candidates AS c
                JOIN elections AS e
                    ON e.election_id = c.election_id
                WHERE c.candidate_id = ? AND c.election_id = ?
                """,
                (candidate_id, election_id),
            ).fetchone()

            if row is None:
                raise CandidateNotFoundError(
                    "Candidate not found in this election"
                )

            if row["election_status"] != "DRAFT":
                raise ElectionLockedError(
                    "Candidate changes require a draft election"
                )

            connection.execute(
                """
                UPDATE candidates
                SET name = ?, party = ?, ballot_order = ?
                WHERE candidate_id = ? AND election_id = ?
                """,
                (
                    values.get("name", row["name"]),
                    values.get("party", row["party"]),
                    values.get("ballot_order", row["ballot_order"]),
                    candidate_id,
                    election_id,
                ),
            )

            updated = connection.execute(
                """
                SELECT candidate_id, election_id, name,
                       party, ballot_order, active
                FROM candidates
                WHERE candidate_id = ? AND election_id = ?
                """,
                (candidate_id, election_id),
            ).fetchone()

            return dict(updated)

    except sqlite3.IntegrityError as error:
        raise CandidateConflictError(
            "Candidate update conflicts with database constraints"
        ) from error

    finally:
        connection.close()

def deactivate_candidate(
    candidate_id,
    election_id,
    db_path=DEFAULT_DB_PATH,
):
    """Mark a candidate inactive without deleting their record."""
    connection = get_connection(db_path)

    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")

            row = connection.execute(
                """
                SELECT c.candidate_id,
                       e.status AS election_status
                FROM candidates AS c
                JOIN elections AS e
                    ON e.election_id = c.election_id
                WHERE c.candidate_id = ? AND c.election_id = ?
                """,
                (candidate_id, election_id),
            ).fetchone()

            if row is None:
                raise CandidateNotFoundError(
                    "Candidate not found in this election"
                )

            if row["election_status"] != "DRAFT":
                raise ElectionLockedError(
                    "Candidate changes require a draft election"
                )

            connection.execute(
                """
                UPDATE candidates
                SET active = 0
                WHERE candidate_id = ? AND election_id = ?
                """,
                (candidate_id, election_id),
            )

            result = connection.execute(
                """
                SELECT candidate_id, election_id, name,
                       party, ballot_order, active
                FROM candidates
                WHERE candidate_id = ? AND election_id = ?
                """,
                (candidate_id, election_id),
            ).fetchone()

            return dict(result)

    finally:
        connection.close()        
if __name__ == "__main__":
    init_db()
    print(f"Candidate database initialised: {DEFAULT_DB_PATH}")