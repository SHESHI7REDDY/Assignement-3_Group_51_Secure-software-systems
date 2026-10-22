"""Public read-only access to finalized, published fictional election results.

Unpublished results are not disclosed. Administrative endpoints have separate
mock access control; this endpoint deliberately accepts no authorization input.
"""
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException

from app.results.repository import get_count, DEFAULT_DB_PATH

router = APIRouter(tags=["results-public"])


@router.get('/{election_id}')
def read_published_result(election_id: str):
    """Return published counts only, with an explicit public response shape."""
    if not election_id or not election_id.strip():
        raise HTTPException(status_code=404, detail="Published result not found")
    db = Path(os.environ.get("RESULTS_DB_PATH", str(DEFAULT_DB_PATH)))
    count = get_count(election_id, db)
    if count is None or count['status'] != 'published':
        # Same response conceals whether an unpublished election exists.
        raise HTTPException(status_code=404, detail="Published result not found")
    return {
        'election_id': count['election_id'],
        'status': 'published',
        'total_ballots': count['total_ballots'],
        'winner_id': count['winner_id'],
        'rounds': count['rounds'],
        'published_at': count['published_at'],
    }
