"""Audit tests operate on disposable SQLite files and test-only keys."""
import sqlite3
import pytest

from app.results.audit import AuditError, append_event, initialize_audit, read_events, verify_audit, GENESIS

KEY = b"test-only-32-byte-secret-key-for-local-qa"


def add(db, kind="COUNT_COMPLETED", election="DEMO-001"):
    return append_event(election, kind, "test-admin", "success", KEY, db)


def test_initialize_idempotently(tmp_path):
    db = tmp_path / "audit.db"
    initialize_audit(db)
    initialize_audit(db)
    assert verify_audit(KEY, db)


def test_empty_log_is_valid(tmp_path):
    assert verify_audit(KEY, tmp_path / "audit.db")


def test_first_event_uses_genesis_and_utc(tmp_path):
    event = add(tmp_path / "audit.db")
    assert event["sequence"] == 1
    assert event["previous_hash"] == GENESIS
    assert event["occurred_at"].endswith("+00:00")


def test_multiple_events_chained(tmp_path):
    db = tmp_path / "audit.db"
    first = add(db, "COUNT_STARTED")
    second = add(db)
    assert second["previous_hash"] == first["integrity_hash"]
    assert verify_audit(KEY, db)


def test_multiple_elections_use_global_chain(tmp_path):
    db = tmp_path / "audit.db"
    add(db, election="DEMO-001")
    add(db, election="DEMO-002")
    assert len(read_events(db, election_id="DEMO-001")) == 1
    assert verify_audit(KEY, db)


def test_detect_modified_event(tmp_path):
    db = tmp_path / "audit.db"
    add(db)
    with sqlite3.connect(db) as con:
        con.execute("UPDATE results_audit_events SET outcome='denied' WHERE sequence=1")
    assert not verify_audit(KEY, db)


def test_detect_deleted_middle_event(tmp_path):
    db = tmp_path / "audit.db"
    for _ in range(3): add(db)
    with sqlite3.connect(db) as con:
        con.execute("DELETE FROM results_audit_events WHERE sequence=2")
    assert not verify_audit(KEY, db)


def test_wrong_key_rejected_by_verifier(tmp_path):
    db = tmp_path / "audit.db"
    add(db)
    assert not verify_audit(b"another-secret-key-that-is-long-enough!", db)


@pytest.mark.parametrize("arguments", [
    {"event_type": "UNKNOWN"}, {"election_id": ""},
    {"actor_id": ""}, {"outcome": "maybe"},
    {"occurred_at": "2026-10-23T12:00:00"},
])
def test_invalid_event_rejected(tmp_path, arguments):
    values = dict(election_id="DEMO-001", event_type="COUNT_STARTED", actor_id="test-admin", outcome="success", occurred_at="2026-10-23T00:00:00+00:00")
    values.update(arguments)
    with pytest.raises(AuditError):
        append_event(key=KEY, db_path=tmp_path / "audit.db", **values)


def test_short_key_rejected(tmp_path):
    with pytest.raises(AuditError):
        append_event("DEMO-001", "COUNT_STARTED", "admin", "success", b"weak", tmp_path / "audit.db")


def test_audit_schema_does_not_store_ballot_details(tmp_path):
    db = tmp_path / "audit.db"
    add(db)
    with sqlite3.connect(db) as con:
        names = {c[1] for c in con.execute("PRAGMA table_info(results_audit_events)")}
    assert not names.intersection({"voter_id", "ballot_id", "preferences", "voter_name"})
