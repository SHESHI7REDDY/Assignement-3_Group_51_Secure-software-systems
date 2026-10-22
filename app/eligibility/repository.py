"""SQLite storage for the eligibility module (owner: Ved).

Seed fictional data:  python -m app.eligibility.repository


Design notes (security):
* `electors` holds identity + enrolment data (the electoral roll).
* `voting_status` holds the one-vote flag. Primary key (election_id, voter_id)
  means the database itself cannot hold two rows for the same voter.
* `ballot_tokens` deliberately has NO voter_id column and stores only a
  SHA-256 hash of the one-time token, so a ballot cannot be traced back to
  a voter through this table (identity is kept separate from the vote).
* `audit_log` is a hash chain: each entry includes the previous entry's hash.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS electors (
    voter_id          TEXT PRIMARY KEY,
    full_name         TEXT NOT NULL,
    date_of_birth     TEXT NOT NULL,
    citizenship       TEXT NOT NULL,
    state             TEXT NOT NULL,
    division          TEXT NOT NULL,
    address           TEXT NOT NULL,
    enrolment_status  TEXT NOT NULL CHECK (enrolment_status IN ('ENROLLED','PENDING','REMOVED')),
    disqualified      INTEGER NOT NULL DEFAULT 0 CHECK (disqualified IN (0,1)),
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS voting_status (
    election_id  TEXT NOT NULL,
    voter_id     TEXT NOT NULL REFERENCES electors(voter_id),
    has_voted    INTEGER NOT NULL DEFAULT 0 CHECK (has_voted IN (0,1)),
    channel      TEXT,
    PRIMARY KEY (election_id, voter_id)
);

CREATE TABLE IF NOT EXISTS ballot_tokens (
    token_hash   TEXT PRIMARY KEY,
    election_id  TEXT NOT NULL,
    division     TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    redeemed     INTEGER NOT NULL DEFAULT 0 CHECK (redeemed IN (0,1))
);

CREATE TABLE IF NOT EXISTS audit_log (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    actor_role   TEXT NOT NULL,
    actor_ref    TEXT NOT NULL,
    action       TEXT NOT NULL,
    subject_ref  TEXT NOT NULL,
    outcome      TEXT NOT NULL,
    prev_hash    TEXT NOT NULL,
    entry_hash   TEXT NOT NULL
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    # isolation_level=None -> we control transactions explicitly (BEGIN IMMEDIATE)
    conn = sqlite3.connect(db_path, timeout=15, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
    finally:
        conn.close()


# ---------------- Fictional seed data (no real people) ----------------
ELECTORS = [
    # voter_id, name, dob, citizenship, state, division, address, status, disqualified
    ("V0001", "Alice Nguyen", "1990-04-12", "AU", "VIC", "Wills", "12 Sample St, Brunswick", "ENROLLED", 0),
    ("V0002", "Ben Carter", "2010-01-01", "AU", "NSW", "Sydney", "4 Test Rd, Ultimo", "ENROLLED", 0),
    ("V0003", "Chloe Smith", "1985-07-30", "NZ", "QLD", "Brisbane", "9 Demo Ave, Spring Hill", "ENROLLED", 0),
    ("V0004", "Dev Patel", "1979-11-02", "AU", "WA", "Perth", "77 Mock Pde, Perth", "ENROLLED", 1),
    ("V0005", "Emma Brown", "2000-02-20", "AU", "SA", "Adelaide", "3 Fake Ln, Adelaide", "PENDING", 0),
    ("V0006", "Farah Ali", "1995-09-09", "AU", "VIC", "Melbourne", "88 Example St, Carlton", "ENROLLED", 0),
    ("V0007", "George Lee", "1968-03-15", "AU", "NSW", "Grayndler", "21 Trial St, Newtown", "ENROLLED", 0),
    ("V0008", "Hana Kim", "2008-12-05", "AU", "ACT", "Canberra", "5 Proto Pl, Braddon", "ENROLLED", 0),
]
# V0006 has already voted in this election.
ALREADY_VOTED = ["V0006"]


def seed(settings) -> None:
    init_db(settings.db_path)
    conn = connect(settings.db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("BEGIN")
    for e in ELECTORS:
        conn.execute("INSERT OR REPLACE INTO electors VALUES (?,?,?,?,?,?,?,?,?,?)", (*e, now))
    for v in ALREADY_VOTED:
        conn.execute("INSERT OR REPLACE INTO voting_status (election_id, voter_id, has_voted, channel)"
                     " VALUES (?,?,1,'POLLING_STATION')", (settings.election_id, v))
    conn.execute("COMMIT")
    conn.close()


if __name__ == "__main__":
    from .config import Settings
    s = Settings()
    seed(s)
    print(f"Seeded {len(ELECTORS)} fictional electors into {s.db_path}")
