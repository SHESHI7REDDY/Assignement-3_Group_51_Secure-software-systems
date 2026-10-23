"""Insert missing fictional roll entries without resetting existing voters."""

from app.eligibility.config import Settings
from app.eligibility.repository import ALREADY_VOTED, ELECTORS, connect, init_db
from datetime import datetime, timezone


def main():
    settings = Settings()
    init_db(settings.db_path)
    connection = connect(settings.db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        now = datetime.now(timezone.utc).isoformat()
        for elector in ELECTORS:
            connection.execute(
                "INSERT OR IGNORE INTO electors VALUES (?,?,?,?,?,?,?,?,?,?)",
                (*elector, now),
            )
        for voter_id in ALREADY_VOTED:
            connection.execute(
                "INSERT OR IGNORE INTO voting_status "
                "(election_id, voter_id, has_voted, channel) VALUES (?,?,1,?)",
                (settings.election_id, voter_id, "POLLING_STATION"),
            )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
    print("Missing fictional electoral-roll entries prepared.")
    print("Existing enrolment and voting records were preserved.")
    print("Election:", settings.election_id)


if __name__ == "__main__":
    main()
