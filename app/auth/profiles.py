"""Trusted links between login accounts and fictional electoral-roll records.

Only the local operator can create demo links. Public registration and login
cannot choose a voter ID, officer role or election assignment.
"""

import argparse
import re
import sqlite3
from contextlib import closing

from app.auth import repository


def initialise_profiles():
    repository.initialise_database()
    with closing(repository.get_connection()) as connection:
        with connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS account_voters (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id),
                    voter_id TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS officer_elections (
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    election_id TEXT NOT NULL,
                    PRIMARY KEY (user_id, election_id)
                );
            """)


def identity_for_user(user):
    """Read identity and scope from server records, never request fields."""
    initialise_profiles()
    with closing(repository.get_connection()) as connection:
        link = connection.execute(
            "SELECT voter_id FROM account_voters WHERE user_id = ?",
            (user["id"],),
        ).fetchone()
        elections = connection.execute(
            "SELECT election_id FROM officer_elections WHERE user_id = ? "
            "ORDER BY election_id",
            (user["id"],),
        ).fetchall()
    return {
        **user,
        "user_id": str(user["id"]),
        "voter_id": link["voter_id"] if link else None,
        "managed_election_ids": (
            [row["election_id"] for row in elections]
            if user["role"] == "officer" else []
        ),
    }


def link_demo_voter(username, voter_id):
    """Link a fictional voter without changing passwords or permissions.

    Repeating the same link is safe. Remapping a linked account, or sharing
    one voter ID across accounts, is rejected.
    """
    if not re.fullmatch(r"V[0-9]{4}", voter_id):
        raise ValueError("Use a fictional voter ID such as V0001")
    initialise_profiles()
    with closing(repository.get_connection()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            user = connection.execute(
                "SELECT id, role FROM users WHERE username = ?", (username,)
            ).fetchone()
            if user is None:
                raise ValueError("Account not found; register it first")
            if user["role"] != "voter":
                raise ValueError("Only voter accounts can use this demo link")
            existing = connection.execute(
                "SELECT voter_id FROM account_voters WHERE user_id = ?",
                (user["id"],),
            ).fetchone()
            if existing:
                if existing["voter_id"] != voter_id:
                    raise ValueError("Account already linked to another voter")
                return
            try:
                connection.execute(
                    "INSERT INTO account_voters(user_id, voter_id) VALUES (?, ?)",
                    (user["id"], voter_id),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Voter ID is already linked to another account") from error


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Link fictional demo accounts only")
    parser.add_argument("username")
    parser.add_argument("voter_id")
    arguments = parser.parse_args()
    try:
        link_demo_voter(arguments.username, arguments.voter_id)
    except ValueError as error:
        parser.exit(1, f"Link rejected: {error}\n")
    print(f"Demo account {arguments.username} linked to {arguments.voter_id}.")
    print("This link does not establish eligibility or grant officer access.")
