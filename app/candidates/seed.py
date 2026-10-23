"""Prepare fictional local demo data.

Names and party assignments are demonstration data only.
Existing demo candidate names and parties are updated when rerun.
"""

from app.candidates.repository import (
    DEFAULT_DB_PATH,
    get_connection,
    init_db,
)


def seed_demo(db_path=DEFAULT_DB_PATH):
    init_db(db_path)
    connection = get_connection(db_path)

    try:
        with connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO elections (election_id, title)
                VALUES (?, ?)
                """,
                ("DEMO-A3-ELECTIONS", "Fictional demonstration election"),
            )

            election = connection.execute(
                "SELECT status FROM elections WHERE election_id = ?",
                ("DEMO-A3-ELECTIONS",),
            ).fetchone()

            if election["status"] != "DRAFT":
                raise ValueError(
                    "Demo candidates can only be seeded "
                    "while the election is DRAFT."
                )

            candidates = [
                ("DEMO-C001", "Varshil", "BRS", 1),
                ("DEMO-C002", "Ved", "TRS", 2),
                ("DEMO-C003", "Akshit", "BJP", 3),
                ("DEMO-C004", "Moinul", "Independent", 4),
            ]

            for candidate_id, name, party, order in candidates:
                connection.execute(
                    """
                    INSERT INTO candidates (
                        candidate_id,
                        election_id,
                        name,
                        party,
                        ballot_order
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(candidate_id) DO UPDATE SET
                        name = excluded.name,
                        party = excluded.party
                    WHERE candidates.election_id = excluded.election_id
                    """,
                    (
                        candidate_id,
                        "DEMO-A3-ELECTIONS",
                        name,
                        party,
                        order,
                    ),
                )

    finally:
        connection.close()


if __name__ == "__main__":
    seed_demo()
    print("Fictional demonstration candidates prepared:")
    print("Varshil — BRS")
    print("Ved — TRS")
    print("Akshit — BJP")
    print("Moinul — Independent")