"""SQLite persistence for candidate management."""

import sqlite3
from pathlib import Path

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


if __name__ == "__main__":
    init_db()
    print(f"Candidate database initialised: {DEFAULT_DB_PATH}")