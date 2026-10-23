"""Live count snapshots and publication, using the existing counting algorithm.

Only the results database is written. Source databases are attached and locked
for a consistent closed-election snapshot. Result, signature and HMAC audit
changes commit together. No decrypted ballots are returned or persisted here.
"""
import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.ballot import service as ballots
from app.ballot.schemas import BallotSubmission
from app.eligibility.config import Settings
from app.shared.config import DATA
from . import audit, repository
from .elimination import EliminationError
from .preferential import count_preferential
from .service import BallotValidationError


SCHEMA = """CREATE TABLE IF NOT EXISTS platform_count_sources (
    election_id TEXT PRIMARY KEY REFERENCES election_results(election_id),
    source_digest TEXT NOT NULL,
    candidates_json TEXT NOT NULL,
    result_mac TEXT NOT NULL
)"""


def configuration():
    try:
        key = bytes.fromhex(os.getenv("RESULTS_AUDIT_HMAC_KEY", ""))
        if len(key) < 32:
            raise ValueError()
    except ValueError:
        raise HTTPException(503, "A persistent results audit key must be configured") from None
    # Separate default database from the earlier fictional fixture API.
    path = Path(os.getenv("RESULTS_DB_PATH", str(DATA / "platform_results.sqlite3")))
    return key, path


@contextmanager
def transaction(db, settings: Settings, candidate_path, *, write=True):
    paths = [Path(db).resolve(), Path(settings.db_path).resolve(), Path(candidate_path).resolve()]
    if len(set(paths)) != 3:
        raise HTTPException(503, "Results and source databases must use separate files")
    if not paths[1].is_file() or not paths[2].is_file():
        raise HTTPException(503, "Election databases are not prepared")
    repository.initialize_database(db)
    audit.initialize_audit(db)
    connection = repository._connect(db)
    try:
        connection.execute(SCHEMA)
        connection.execute("ATTACH DATABASE ? AS roll_data", (str(paths[1]),))
        connection.execute("ATTACH DATABASE ? AS candidate_data", (str(paths[2]),))
        connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield connection
        connection.commit()
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()


def require_closed(connection, election_id):
    row = connection.execute("SELECT status FROM candidate_data.elections WHERE election_id = ?",
                             (election_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Election not found")
    if row["status"] != "CLOSED":
        raise HTTPException(409, "Close the election before counting or publishing")


def source(connection, election_id):
    candidates = [dict(row) for row in connection.execute(
        "SELECT candidate_id, name, party, ballot_order FROM candidate_data.candidates "
        "WHERE election_id = ? AND active = 1 ORDER BY ballot_order, candidate_id", (election_id,))]
    exists = connection.execute("SELECT 1 FROM roll_data.sqlite_master WHERE type='table' "
                                "AND name='accepted_ballots'").fetchone()
    rows = [dict(row) for row in connection.execute(
        "SELECT ballot_id, election_id, encrypted_ballot FROM roll_data.accepted_ballots "
        "WHERE election_id = ? ORDER BY ballot_id", (election_id,))] if exists else []
    canonical = json.dumps({"election_id": election_id, "candidates": candidates, "ballots": rows},
                           sort_keys=True, separators=(",", ":"), allow_nan=False)
    return candidates, rows, hashlib.sha256(canonical.encode()).hexdigest()


def signing_value(result, source_digest, candidates_json, key):
    payload = json.dumps({"result": result, "source_digest": source_digest,
                          "candidates_json": candidates_json}, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def ensure_audit(connection, key):
    if not audit.verify_audit(key, connection=connection):
        raise HTTPException(409, "Audit integrity verification failed")


def verified_result(connection, election_id, key):
    result = repository.get_count(election_id, connection=connection)
    if result is None:
        return None, None
    snapshot = connection.execute("SELECT * FROM platform_count_sources WHERE election_id = ?",
                                  (election_id,)).fetchone()
    if snapshot is None or not hmac.compare_digest(
        snapshot["result_mac"], signing_value(result, snapshot["source_digest"], snapshot["candidates_json"], key)
    ):
        raise HTTPException(409, "Result integrity verification failed")
    return result, snapshot


def count(connection, settings, actor_id, key):
    require_closed(connection, settings.election_id)
    ensure_audit(connection, key)
    if repository.get_count(settings.election_id, connection=connection) is not None:
        raise HTTPException(409, "Results already counted for this election")
    candidates, rows, digest = source(connection, settings.election_id)
    if not candidates or not rows:
        raise HTTPException(409, "Counting requires active candidates and accepted ballots")
    # Counting must not create or replace an encryption key.
    key_path = Path(os.getenv("BALLOT_KEY_FILE", str(DATA / "ballot_key.key")))
    cipher = Fernet(key_path.read_bytes())
    decoded = []
    for row in rows:
        payload = json.loads(cipher.decrypt(row["encrypted_ballot"].encode()))
        if not isinstance(payload, dict) or set(payload) != {"preferences"}:
            raise ValueError("Unexpected encrypted ballot format")
        ballot = BallotSubmission.model_validate({"election_id": settings.election_id, **payload})
        try:
            ballots.validate_ballot(ballot, candidates)
        except HTTPException as error:
            raise BallotValidationError("Invalid persisted ranking") from error
        decoded.append({"ballot_id": row["ballot_id"], "election_id": settings.election_id,
                        "preferences": [p.candidate_id for p in sorted(ballot.preferences, key=lambda p: p.rank)]})
    result = count_preferential({"election_id": settings.election_id, "candidates": candidates},
                                {"election_id": settings.election_id, "ballots": decoded})
    repository.save_count(result, connection=connection)
    saved = repository.get_count(settings.election_id, connection=connection)
    candidates_json = json.dumps(candidates, sort_keys=True, separators=(",", ":"))
    signature = signing_value(saved, digest, candidates_json, key)
    connection.execute("INSERT INTO platform_count_sources VALUES (?, ?, ?, ?)",
                       (settings.election_id, digest, candidates_json, signature))
    audit.append_event(settings.election_id, "COUNT_COMPLETED", actor_id, "success", key,
                       connection=connection)
    return {**saved, "candidates": candidates}


def publish(connection, election_id, actor_id, key):
    require_closed(connection, election_id)
    ensure_audit(connection, key)
    existing, snapshot = verified_result(connection, election_id, key)
    if existing is None:
        raise HTTPException(404, "Election results not found")
    if existing["status"] != "counted":
        raise HTTPException(409, "Election results already published")
    _, _, digest = source(connection, election_id)
    if not hmac.compare_digest(digest, snapshot["source_digest"]):
        raise HTTPException(409, "Election data changed after counting; publication blocked")
    result = repository.publish_count(election_id, connection=connection)
    signature = signing_value(result, snapshot["source_digest"], snapshot["candidates_json"], key)
    connection.execute("UPDATE platform_count_sources SET result_mac = ? WHERE election_id = ?",
                       (signature, election_id))
    audit.append_event(election_id, "RESULT_PUBLISHED", actor_id, "success", key, connection=connection)
    return {**result, "candidates": json.loads(snapshot["candidates_json"])}


def public_result(connection, election_id, key):
    ensure_audit(connection, key)
    result, snapshot = verified_result(connection, election_id, key)
    if result is None or result["status"] != "published":
        raise HTTPException(404, "Published result not found")
    require_closed(connection, election_id)
    _, _, digest = source(connection, election_id)
    if not hmac.compare_digest(digest, snapshot["source_digest"]):
        raise HTTPException(409, "Election data changed after counting")
    return {name: result[name] for name in ("election_id", "status", "total_ballots", "winner_id",
                                            "rounds", "published_at")} | {"candidates": json.loads(snapshot["candidates_json"])}


def operation(action, db, settings, candidate_path, *args):
    """One transaction for every result/audit mutation; failures roll back both."""
    try:
        with transaction(db, settings, candidate_path, write=action in (count, publish)) as connection:
            return action(connection, *args)
    except HTTPException:
        raise
    except EliminationError as error:
        raise HTTPException(409, "Unresolved elimination tie; a reviewed tie procedure is required") from error
    except (InvalidToken, BallotValidationError, ValueError, TypeError, KeyError) as error:
        raise HTTPException(409, "Invalid ballot or result data; no result changes were saved") from error
    except (OSError, sqlite3.Error, RuntimeError) as error:
        raise HTTPException(503, "Results operation unavailable; no result changes were saved") from error
