"""Dynamic preference validation and authenticated ballot encryption."""
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.shared.config import DATA


def validate_ballot(ballot, candidates):
    expected = {row["candidate_id"] for row in candidates}
    ids = [item.candidate_id for item in ballot.preferences]
    ranks = [item.rank for item in ballot.preferences]
    if not expected or len(ids) != len(expected) or set(ids) != expected:
        raise HTTPException(400, "Rank every active candidate exactly once")
    if sorted(ranks) != list(range(1, len(expected) + 1)):
        raise HTTPException(400, "Use each preference number exactly once")


def build_anonymous_ballot_payload(ballot):
    return {"preferences": [item.model_dump() for item in ballot.preferences]}


def encrypt_ballot(ballot, cipher):
    payload = json.dumps(build_anonymous_ballot_payload(ballot), sort_keys=True)
    return cipher.encrypt(payload.encode("utf-8")).decode("ascii")


def load_cipher(connection):
    """Create one persistent local key. Never replace a lost key after voting."""
    path = Path(os.getenv("BALLOT_KEY_FILE", str(DATA / "ballot_key.key")))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        if connection.execute("SELECT 1 FROM accepted_ballots LIMIT 1").fetchone():
            raise ValueError("Ballot key is missing; restore the existing key")
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "wb") as key_file:
                key_file.write(Fernet.generate_key())
    return Fernet(path.read_bytes())
