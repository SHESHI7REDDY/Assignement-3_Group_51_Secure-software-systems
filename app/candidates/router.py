"""Candidate APIs. Management operations remain unimplemented."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.candidates.repository import DEFAULT_DB_PATH, list_candidates
from app.shared.placeholders import unfinished


router = APIRouter(prefix="/candidates", tags=["candidates"])


def get_db_path():
    return DEFAULT_DB_PATH


@router.get("")
def get_candidates(
    election_id: Annotated[
        str,
        Query(
            min_length=1,
            max_length=64,
            pattern=r"^[A-Za-z0-9_-]+$",
        ),
    ],
    db_path: Path = Depends(get_db_path),
):
    candidates = list_candidates(election_id, db_path)

    if candidates is None:
        raise HTTPException(status_code=404, detail="Election not found")

    return {
        "election_id": election_id,
        "candidates": candidates,
    }


@router.post("")
def create_candidate():
    unfinished("candidates")


@router.patch("/{candidate_id}")
def update_candidate(candidate_id: str):
    unfinished("candidates")