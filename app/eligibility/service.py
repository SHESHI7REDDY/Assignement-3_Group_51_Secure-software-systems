"""Business logic: eligibility rules (ELIG-01) and the atomic one-vote rule (ELIG-02)."""
from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from . import audit
from .config import Settings
from .security import Principal, hash_token, pseudonymise

# Generic reason codes returned to callers. Detailed personal data is never echoed back.
ELIGIBLE = "ELIGIBLE"
NOT_ENROLLED = "NOT_ENROLLED"
NOT_ELIGIBLE = "NOT_ELIGIBLE"
ALREADY_VOTED = "ALREADY_VOTED"


class AlreadyVoted(Exception):
    pass


class NotEligible(Exception):
    def __init__(self, reason: str):
        self.reason = reason


class NotFound(Exception):
    pass


@dataclass
class Decision:
    eligible: bool
    reason: str
    detail: str  # internal only (audit), never returned to the client


def age_on(dob: date, on: date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def evaluate(elector: sqlite3.Row | None, has_voted: bool, election_date: date) -> Decision:
    """Deny-by-default rule engine. Every rule must pass for ELIGIBLE."""
    if elector is None:
        return Decision(False, NOT_ENROLLED, "no_record")
    if elector["enrolment_status"] != "ENROLLED":
        return Decision(False, NOT_ENROLLED, "status_" + elector["enrolment_status"].lower())
    if elector["citizenship"] != "AU":
        return Decision(False, NOT_ELIGIBLE, "not_citizen")
    if age_on(date.fromisoformat(elector["date_of_birth"]), election_date) < 18:
        return Decision(False, NOT_ELIGIBLE, "under_18")
    if elector["disqualified"]:
        return Decision(False, NOT_ELIGIBLE, "disqualified")
    if has_voted:
        return Decision(False, ALREADY_VOTED, "already_voted")
    return Decision(True, ELIGIBLE, "all_rules_passed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load(conn, settings: Settings, voter_id: str):
    elector = conn.execute("SELECT * FROM electors WHERE voter_id = ?", (voter_id,)).fetchone()
    row = conn.execute("SELECT has_voted FROM voting_status WHERE election_id = ? AND voter_id = ?",
                       (settings.election_id, voter_id)).fetchone()
    return elector, bool(row and row["has_voted"])


def check(conn, settings: Settings, actor: Principal, voter_id: str) -> Decision:
    elector, voted = _load(conn, settings, voter_id)
    decision = evaluate(elector, voted, settings.election_date)
    conn.execute("BEGIN IMMEDIATE")
    audit.append(conn, actor.role, pseudonymise(settings, actor.user_id), "CHECK",
                 pseudonymise(settings, voter_id), f"{decision.reason}:{decision.detail}")
    conn.execute("COMMIT")
    return decision


def authorise_to_vote(conn, settings: Settings, actor: Principal, voter_id: str, channel: str) -> dict:
    """Atomically: re-check eligibility, mark the voter as voted, and issue a
    single-use ballot token that is NOT linked to the voter.

    Race-condition protection (three layers):
      1. BEGIN IMMEDIATE takes the database write lock before reading.
      2. Conditional UPDATE ... WHERE has_voted = 0; rowcount must be exactly 1.
      3. PRIMARY KEY (election_id, voter_id) prevents duplicate status rows.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        elector, voted = _load(conn, settings, voter_id)
        decision = evaluate(elector, voted, settings.election_date)
        subject = pseudonymise(settings, voter_id)
        actor_ref = pseudonymise(settings, actor.user_id)
        if not decision.eligible:
            audit.append(conn, actor.role, actor_ref, "AUTHORISE", subject,
                         f"DENIED:{decision.reason}:{decision.detail}")
            conn.execute("COMMIT")
            if decision.reason == ALREADY_VOTED:
                raise AlreadyVoted()
            raise NotEligible(decision.reason)

        conn.execute("INSERT OR IGNORE INTO voting_status (election_id, voter_id, has_voted) VALUES (?,?,0)",
                     (settings.election_id, voter_id))
        cur = conn.execute(
            "UPDATE voting_status SET has_voted = 1, channel = ? "
            "WHERE election_id = ? AND voter_id = ? AND has_voted = 0",
            (channel, settings.election_id, voter_id))
        if cur.rowcount != 1:
            audit.append(conn, actor.role, actor_ref, "AUTHORISE", subject, "DENIED:ALREADY_VOTED:race")
            conn.execute("COMMIT")
            raise AlreadyVoted()

        token = secrets.token_urlsafe(32)  # 256-bit CSPRNG token
        expires = (_now() + timedelta(seconds=settings.ballot_token_ttl_seconds)).replace(second=0, microsecond=0)
        conn.execute("INSERT INTO ballot_tokens (token_hash, election_id, division, expires_at) VALUES (?,?,?,?)",
                     (hash_token(token), settings.election_id, elector["division"], expires.isoformat()))
        audit.append(conn, actor.role, actor_ref, "AUTHORISE", subject, "GRANTED")
        conn.execute("COMMIT")
        return {"ballot_token": token, "election_id": settings.election_id,
                "division": elector["division"], "expires_at": expires.isoformat()}
    except (AlreadyVoted, NotEligible):
        raise
    except Exception:
        conn.execute("ROLLBACK")
        raise


def redeem_token(conn, settings: Settings, actor: Principal, token: str) -> dict | None:
    """Called by the Ballot module. Single use: conditional UPDATE on redeemed = 0."""
    h = hash_token(token)
    conn.execute("BEGIN IMMEDIATE")
    cur = conn.execute(
        "UPDATE ballot_tokens SET redeemed = 1 WHERE token_hash = ? AND redeemed = 0 AND expires_at > ?",
        (h, _now().isoformat()))
    ok = cur.rowcount == 1
    row = conn.execute("SELECT election_id, division FROM ballot_tokens WHERE token_hash = ?", (h,)).fetchone() if ok else None
    audit.append(conn, actor.role, pseudonymise(settings, actor.user_id), "REDEEM_TOKEN",
                 h[:20], "ACCEPTED" if ok else "REJECTED")
    conn.execute("COMMIT")
    return dict(row) if row else None


def enrol(conn, settings: Settings, actor: Principal, data: dict) -> str:
    status_value = "ENROLLED" if actor.role == "officer" else "PENDING"
    conn.execute("BEGIN IMMEDIATE")
    try:
        exists = conn.execute("SELECT 1 FROM electors WHERE voter_id = ?", (data["voter_id"],)).fetchone()
        if exists:
            conn.execute("ROLLBACK")
            raise ValueError("already enrolled")
        conn.execute(
            "INSERT INTO electors (voter_id, full_name, date_of_birth, citizenship, state, division, address,"
            " enrolment_status, disqualified, updated_at) VALUES (?,?,?,?,?,?,?,?,0,?)",
            (data["voter_id"], data["full_name"], data["date_of_birth"].isoformat(), data["citizenship"],
             data["state"], data["division"], data["address"], status_value, _now().isoformat()))
        audit.append(conn, actor.role, pseudonymise(settings, actor.user_id), "ENROL",
                     pseudonymise(settings, data["voter_id"]), status_value)
        conn.execute("COMMIT")
        return status_value
    except ValueError:
        raise
    except Exception:
        conn.execute("ROLLBACK")
        raise


def approve(conn, settings: Settings, actor: Principal, voter_id: str) -> None:
    conn.execute("BEGIN IMMEDIATE")
    cur = conn.execute("UPDATE electors SET enrolment_status = 'ENROLLED', updated_at = ? "
                       "WHERE voter_id = ? AND enrolment_status = 'PENDING'", (_now().isoformat(), voter_id))
    audit.append(conn, actor.role, pseudonymise(settings, actor.user_id), "APPROVE",
                 pseudonymise(settings, voter_id), "OK" if cur.rowcount else "NO_PENDING")
    conn.execute("COMMIT")
    if cur.rowcount != 1:
        raise NotFound()


def update_address(conn, settings: Settings, actor: Principal, voter_id: str, address: str, division: str) -> None:
    conn.execute("BEGIN IMMEDIATE")
    cur = conn.execute("UPDATE electors SET address = ?, division = ?, updated_at = ? WHERE voter_id = ?",
                       (address, division, _now().isoformat(), voter_id))
    audit.append(conn, actor.role, pseudonymise(settings, actor.user_id), "UPDATE_ADDRESS",
                 pseudonymise(settings, voter_id), "OK" if cur.rowcount else "NOT_FOUND")
    conn.execute("COMMIT")
    if cur.rowcount != 1:
        raise NotFound()
