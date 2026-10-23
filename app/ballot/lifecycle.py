"""Trusted local operator command for the fictional election lifecycle.

This command requires access to the server's database files. There is no
public API to change election state. CLOSED elections cannot be reopened.
"""
import argparse
from contextlib import closing
from app.candidates.repository import DEFAULT_DB_PATH, get_connection


def transition(election_id, target, db_path=DEFAULT_DB_PATH):
    with closing(get_connection(db_path)) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status FROM elections WHERE election_id = ?",
                                     (election_id,)).fetchone()
            if row is None:
                raise ValueError("Election not found; prepare the candidate database first")
            current = row["status"]
            if current == target:
                return
            if (current, target) not in {("DRAFT", "OPEN"), ("OPEN", "CLOSED")}:
                raise ValueError("Only DRAFT to OPEN and OPEN to CLOSED are allowed")
            if target == "OPEN" and not connection.execute(
                "SELECT 1 FROM candidates WHERE election_id = ? AND active = 1", (election_id,)
            ).fetchone():
                raise ValueError("Prepare active candidates before opening the election")
            connection.execute("UPDATE elections SET status = ? WHERE election_id = ?", (target, election_id))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("election_id")
    parser.add_argument("status", choices=["OPEN", "CLOSED"])
    args = parser.parse_args()
    try:
        transition(args.election_id, args.status)
    except ValueError as error:
        parser.exit(1, f"State change rejected: {error}\n")
    print(f"Election {args.election_id}: {args.status}")
