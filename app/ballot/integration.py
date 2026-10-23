"""One transaction: eligibility, one-use token, redemption and encrypted ballot.

Only the eligibility database is written. The attached candidate database is
locked while reading its election state and candidate list, preventing a
candidate change or election closure from racing an accepted vote.
"""
import sqlite3
import uuid
from contextlib import closing

from fastapi import HTTPException

from app.candidates.repository import DEFAULT_DB_PATH
from app.eligibility import repository as roll, service as eligibility
from app.eligibility.security import Principal
from . import repository, service


def get_candidate_db_path():
    return DEFAULT_DB_PATH


def open_connection(settings, candidate_db_path):
    # Fail if the configured candidate database has not been prepared.
    path = candidate_db_path.resolve()
    if not path.is_file():
        raise HTTPException(503, "Candidate database is not prepared")
    roll.init_db(settings.db_path)
    connection = roll.connect(settings.db_path)
    try:
        repository.initialise_database(connection)
        connection.execute("ATTACH DATABASE ? AS candidate_data", (str(path),))
        return connection
    except Exception:
        connection.close()
        raise


def read_catalog(connection, election_id):
    election = connection.execute(
        "SELECT title, status FROM candidate_data.elections WHERE election_id = ?",
        (election_id,),
    ).fetchone()
    if election is None:
        raise HTTPException(404, "Election not found")
    rows = connection.execute(
        "SELECT candidate_id, name, party, ballot_order FROM candidate_data.candidates "
        "WHERE election_id = ? AND active = 1 ORDER BY ballot_order, candidate_id",
        (election_id,),
    ).fetchall()
    return dict(election), [dict(row) for row in rows]


def catalog(settings, candidate_db_path):
    with closing(open_connection(settings, candidate_db_path)) as connection:
        connection.execute("BEGIN")
        election, candidates = read_catalog(connection, settings.election_id)
        connection.execute("COMMIT")
        return {"election_id": settings.election_id, **election, "candidates": candidates}


def require_open(connection, settings, ballot):
    if ballot.election_id != settings.election_id:
        raise HTTPException(400, "Ballot does not match the configured election")
    election, candidates = read_catalog(connection, ballot.election_id)
    if election["status"] != "OPEN":
        raise HTTPException(409, "Election is not open for voting")
    service.validate_ballot(ballot, candidates)


def submit(ballot, identity, settings, candidate_db_path):
    with closing(open_connection(settings, candidate_db_path)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            require_open(connection, settings, ballot)
            cipher = service.load_cipher(connection)
            encrypted = service.encrypt_ballot(ballot, cipher)
            actor = Principal(user_id=identity["user_id"], role="voter", voter_id=identity["voter_id"])
            grant = eligibility.authorise_to_vote(
                connection, settings, actor, identity["voter_id"], "ONLINE", manage_transaction=False,
            )
            redeemed = eligibility.redeem_token(
                connection, settings, Principal(user_id="ballot-service", role="service"),
                grant["ballot_token"], manage_transaction=False,
            )
            if not redeemed or redeemed["election_id"] != ballot.election_id:
                raise RuntimeError("Ballot authorisation could not be redeemed")
            receipt = uuid.uuid4().hex
            repository.save_ballot(connection, ballot.election_id, encrypted, receipt)
            connection.execute("COMMIT")
            return {"message": "Ballot accepted and securely stored", "ballot_id": receipt,
                    "election_id": ballot.election_id}
        except eligibility.AlreadyVoted:
            raise HTTPException(409, "ALREADY_VOTED")
        except eligibility.NotEligible as error:
            raise HTTPException(403, error.reason)
        except (sqlite3.Error, OSError, ValueError, RuntimeError) as error:
            # No database details, key paths, tokens or preferences in responses.
            raise HTTPException(503, "Ballot could not be stored; your vote was not used") from error
        finally:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
