"""Tamper-evident, HMAC-linked events for the fictional results prototype.

Requires a caller-managed secret key. Never store the key in SQLite or Git.
HMAC chains are tamper-evident only while the key is kept separate from the DB.
Whole-tail truncation needs an external trusted checkpoint to be detectable.
"""
from contextlib import closing, nullcontext
import hashlib
import hmac
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.results.repository import DEFAULT_DB_PATH, _connect

GENESIS = "0" * 64
ALLOWED_EVENTS = frozenset({"COUNT_STARTED", "COUNT_COMPLETED", "RESULT_PUBLISHED", "PUBLICATION_DENIED", "AUDIT_VERIFICATION_FAILED"})


class AuditError(ValueError):
    """Invalid audit data or cryptographic configuration."""


def _key(key: bytes) -> bytes:
    if not isinstance(key, bytes) or len(key) < 32:
        raise AuditError("Audit HMAC key must be at least 32 random bytes")
    return key


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _mac(key: bytes, prev_hash: str, payload: dict) -> str:
    return hmac.new(key, prev_hash.encode("ascii") + b"\n" + _canonical(payload), hashlib.sha256).hexdigest()


def initialize_audit(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    with _connect(db_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS results_audit_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            integrity_hash TEXT NOT NULL
        )""")


def append_event(election_id: str, event_type: str, actor_id: str, outcome: str,
                 key: bytes, db_path: str | Path = DEFAULT_DB_PATH,
                 *, occurred_at: str | None = None, connection=None) -> dict:
    """Append a signed event in one SQLite write transaction."""
    key = _key(key)
    if not isinstance(election_id, str) or not election_id.strip():
        raise AuditError("election_id is required")
    if event_type not in ALLOWED_EVENTS:
        raise AuditError("Unrecognized audit event type")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise AuditError("actor_id is required")
    if outcome not in ("success", "denied", "failure"):
        raise AuditError("Invalid audit outcome")
    timestamp = occurred_at or datetime.now(timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError) as exc:
        raise AuditError("Invalid audit timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise AuditError("Audit timestamp must be UTC")
    if connection is None:
        initialize_audit(db_path)
    elif not connection.in_transaction:
        raise AuditError("An outer transaction is required")
    scope = nullcontext(connection) if connection is not None else closing(_connect(db_path))
    with scope as con:
        if connection is None:
            con.execute("BEGIN IMMEDIATE")
        last = con.execute("SELECT sequence, integrity_hash FROM results_audit_events ORDER BY sequence DESC LIMIT 1").fetchone()
        sequence = (last["sequence"] + 1) if last else 1
        prev = last["integrity_hash"] if last else GENESIS
        payload = {"sequence": sequence, "election_id": election_id,
                   "event_type": event_type, "actor_id": actor_id,
                   "outcome": outcome, "occurred_at": timestamp}
        digest = _mac(key, prev, payload)
        con.execute("""INSERT INTO results_audit_events
            (sequence, election_id, event_type, actor_id, outcome, occurred_at, previous_hash, integrity_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (sequence, election_id, event_type, actor_id, outcome, timestamp, prev, digest))
        if connection is None:
            con.commit()
        return {**payload, "previous_hash": prev, "integrity_hash": digest}


def read_events(db_path: str | Path = DEFAULT_DB_PATH, *, election_id: str | None = None,
                connection=None) -> list[dict]:
    if connection is None:
        initialize_audit(db_path)
    scope = nullcontext(connection) if connection is not None else closing(_connect(db_path))
    with scope as con:
        if election_id is None:
            rows = con.execute("SELECT * FROM results_audit_events ORDER BY sequence").fetchall()
        else:
            rows = con.execute("SELECT * FROM results_audit_events WHERE election_id = ? ORDER BY sequence", (election_id,)).fetchall()
    return [dict(row) for row in rows]


def verify_audit(key: bytes, db_path: str | Path = DEFAULT_DB_PATH, *, connection=None) -> bool:
    """Verify the entire global chain (do not filter by election before verifying)."""
    key = _key(key)
    rows = read_events(db_path, connection=connection)
    prior = GENESIS
    for expected_sequence, row in enumerate(rows, start=1):
        if row["sequence"] != expected_sequence or not hmac.compare_digest(row["previous_hash"], prior):
            return False
        payload = {k: row[k] for k in ("sequence", "election_id", "event_type", "actor_id", "outcome", "occurred_at")}
        if not hmac.compare_digest(_mac(key, prior, payload), row["integrity_hash"]):
            return False
        prior = row["integrity_hash"]
    return True
