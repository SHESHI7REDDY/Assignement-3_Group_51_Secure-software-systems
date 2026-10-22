"""SQLite persistence of fictional election count snapshots.

Only anonymous count summaries are stored; no voter identifiers or raw ballots.
The caller supplies a database path for test isolation.
"""
import json
import sqlite3
from pathlib import Path
from typing import Mapping

from app.shared.config import DATA

DEFAULT_DB_PATH = DATA / "results.sqlite3"


class ResultStorageError(ValueError):
    """An invalid or conflicting result was supplied to the repository."""


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create the count-results table without disturbing existing records."""
    with _connect(db_path) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS election_results (
                election_id TEXT PRIMARY KEY NOT NULL,
                total_ballots INTEGER NOT NULL CHECK (total_ballots >= 1),
                winner_id TEXT NOT NULL,
                rounds_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'counted'
                    CHECK (status IN ('counted', 'published')),
                counted_at TEXT NOT NULL,
                published_at TEXT
            )
        """)


def save_count(result: Mapping, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Insert a count atomically; never overwrite a finalized count.

    Publication will be implemented separately in a later milestone.
    """
    election_id = result.get("election_id")
    winner = result.get("winner_id")
    total = result.get("total_ballots")
    rounds = result.get("rounds")
    if not isinstance(election_id, str) or not election_id.strip():
        raise ResultStorageError("election_id must be a nonempty string")
    if not isinstance(winner, str) or not winner.strip():
        raise ResultStorageError("winner_id must be a nonempty string")
    if type(total) is not int or total < 1:
        raise ResultStorageError("total_ballots must be a positive integer")
    if not isinstance(rounds, list) or not rounds:
        raise ResultStorageError("rounds must be a nonempty list")
    try:
        rounds_json = json.dumps(rounds, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ResultStorageError("rounds must be JSON serializable") from exc
    from datetime import datetime, timezone
    counted_at = datetime.now(timezone.utc).isoformat()
    initialize_database(db_path)
    try:
        with _connect(db_path) as con:
            con.execute("""
                INSERT INTO election_results
                    (election_id, total_ballots, winner_id, rounds_json, counted_at)
                VALUES (?, ?, ?, ?, ?)
            """, (election_id, total, winner, rounds_json, counted_at))
    except sqlite3.IntegrityError as exc:
        raise ResultStorageError("A result for this election already exists") from exc


def get_count(election_id: str, db_path: str | Path = DEFAULT_DB_PATH) -> dict | None:
    """Return a stored count including publication status, or None if missing.

    This internal function must only be exposed via an authorized API route.
    """
    initialize_database(db_path)
    with _connect(db_path) as con:
        row = con.execute("""
            SELECT election_id, total_ballots, winner_id, rounds_json,
                   status, counted_at, published_at
              FROM election_results WHERE election_id = ?
        """, (election_id,)).fetchone()
    if row is None:
        return None
    return {
        "election_id": row["election_id"],
        "total_ballots": row["total_ballots"],
        "winner_id": row["winner_id"],
        "rounds": json.loads(row["rounds_json"]),
        "status": row["status"],
        "counted_at": row["counted_at"],
        "published_at": row["published_at"],
    }


def publish_count(election_id: str, db_path: str | Path = DEFAULT_DB_PATH) -> dict:
    """Publish exactly one existing counted election; never publish twice."""
    if not isinstance(election_id, str) or not election_id.strip():
        raise ResultStorageError("Valid election_id is required")
    initialize_database(db_path)
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as con:
        con.execute("BEGIN IMMEDIATE")
        cursor = con.execute("""
            UPDATE election_results SET status = 'published', published_at = ?
            WHERE election_id = ? AND status = 'counted'
        """, (stamp, election_id))
        if cursor.rowcount != 1:
            row = con.execute("SELECT status FROM election_results WHERE election_id = ?", (election_id,)).fetchone()
            if row is None:
                raise ResultStorageError("Election results not found")
            raise ResultStorageError("Election results already published")
    return get_count(election_id, db_path)
