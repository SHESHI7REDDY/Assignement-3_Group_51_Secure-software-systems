"""Trusted local setup for a separate fictional results administrator.

Public registration never grants this role. This command requires local access
to server database files; it does not change passwords or voter links.
"""
import argparse
from contextlib import closing
from app.auth import repository
from app.auth.profiles import initialise_profiles


def grant(username):
    initialise_profiles()
    with closing(repository.get_connection()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            user = connection.execute("SELECT id, role FROM users WHERE username = ?", (username,)).fetchone()
            if user is None:
                raise ValueError("Register a separate results administrator account first")
            if user["role"] not in ("voter", "admin"):
                raise ValueError("Use a separate account, not an officer account")
            if connection.execute("SELECT 1 FROM account_voters WHERE user_id = ?", (user["id"],)).fetchone():
                raise ValueError("A linked voter account cannot become the demo administrator")
            if connection.execute("SELECT 1 FROM officer_elections WHERE user_id = ?", (user["id"],)).fetchone():
                raise ValueError("An assigned officer account cannot become the demo administrator")
            if user["role"] != "admin":
                connection.execute("UPDATE users SET role='admin' WHERE id = ?", (user["id"],))
                connection.execute("UPDATE auth_sessions SET revoked=1 WHERE user_id = ?", (user["id"],))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    args = parser.parse_args()
    try:
        grant(args.username)
    except ValueError as error:
        parser.exit(1, f"Administrator setup rejected: {error}\n")
    print(f"Demo administrator {args.username} prepared. Log in again to use the role.")
