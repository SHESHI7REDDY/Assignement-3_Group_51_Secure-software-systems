"""Tamper-evident, privacy-preserving audit log (ELIG-04).

Every entry stores SHA-256(prev_hash | fields). Changing, deleting or
re-ordering any past entry breaks the chain, which verify_chain() detects.
Subjects are stored as keyed pseudonyms, never as raw voter IDs or names.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone

GENESIS = "0" * 64


def _entry_hash(prev_hash: str, ts: str, actor_role: str, actor_ref: str,
                action: str, subject_ref: str, outcome: str) -> str:
    payload = "|".join([prev_hash, ts, actor_role, actor_ref, action, subject_ref, outcome])
    return hashlib.sha256(payload.encode()).hexdigest()


def append(conn: sqlite3.Connection, actor_role: str, actor_ref: str, action: str,
           subject_ref: str, outcome: str) -> None:
    """Must be called inside the caller's transaction so the audit entry and the
    state change commit (or roll back) together."""
    row = conn.execute("SELECT entry_hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
    prev = row["entry_hash"] if row else GENESIS
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    h = _entry_hash(prev, ts, actor_role, actor_ref, action, subject_ref, outcome)
    conn.execute(
        "INSERT INTO audit_log (ts, actor_role, actor_ref, action, subject_ref, outcome, prev_hash, entry_hash)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (ts, actor_role, actor_ref, action, subject_ref, outcome, prev, h),
    )


def verify_chain(conn: sqlite3.Connection) -> dict:
    prev = GENESIS
    count = 0
    for r in conn.execute("SELECT * FROM audit_log ORDER BY seq"):
        expected = _entry_hash(prev, r["ts"], r["actor_role"], r["actor_ref"], r["action"],
                               r["subject_ref"], r["outcome"])
        if r["prev_hash"] != prev or r["entry_hash"] != expected:
            return {"valid": False, "entries": count, "broken_at_seq": r["seq"]}
        prev = r["entry_hash"]
        count += 1
    return {"valid": True, "entries": count, "broken_at_seq": None}
