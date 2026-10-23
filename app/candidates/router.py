"""Candidate listing, protected creation and editing APIs."""

from pathlib import Path
from typing import Annotated
from app.candidates.repository import (
    deactivate_candidate as save_candidate_deactivation,
)
from fastapi import APIRouter, Depends, HTTPException, Query

from app.candidates.repository import (
    DEFAULT_DB_PATH,
    CandidateConflictError,
    CandidateNotFoundError,
    ElectionLockedError,
    ElectionNotFoundError,
    create_candidate as save_candidate,
    list_candidates,
    update_candidate as save_candidate_update,
)
from app.candidates.schemas import CandidateCreate, CandidateUpdate
from app.candidates.security import (
    Identity,
    ensure_election_permission,
    require_candidate_manager,
)


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
        raise HTTPException(
            status_code=404,
            detail="Election not found",
        )

    return {
        "election_id": election_id,
        "candidates": candidates,
    }


@router.post("", status_code=201)
def create_candidate(
    candidate: CandidateCreate,
    identity: Identity = Depends(require_candidate_manager),
    db_path: Path = Depends(get_db_path),
):
    ensure_election_permission(identity, candidate.election_id)

    try:
        return save_candidate(candidate, db_path)

    except ElectionNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Election not found",
        )

    except ElectionLockedError:
        raise HTTPException(
            status_code=409,
            detail="Candidate changes require a draft election",
        )

    except CandidateConflictError:
        raise HTTPException(
            status_code=409,
            detail="Candidate data conflicts with existing records",
        )


@router.patch("/{candidate_id}")
def update_candidate(
    candidate_id: str,
    changes: CandidateUpdate,
    election_id: Annotated[
        str,
        Query(
            min_length=1,
            max_length=64,
            pattern=r"^[A-Za-z0-9_-]+$",
        ),
    ],
    identity: Identity = Depends(require_candidate_manager),
    db_path: Path = Depends(get_db_path),
):
    ensure_election_permission(identity, election_id)

    try:
        return save_candidate_update(
            candidate_id,
            election_id,
            changes,
            db_path,
        )

    except CandidateNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found in this election",
        )

    except ElectionLockedError:
        raise HTTPException(
            status_code=409,
            detail="Candidate changes require a draft election",
        )

    except CandidateConflictError:
        raise HTTPException(
            status_code=409,
            detail="Candidate data conflicts with existing records",
        )

@router.post("/{candidate_id}/deactivate")
def deactivate_candidate(
    candidate_id: str,
    election_id: Annotated[
        str,
        Query(
            min_length=1,
            max_length=64,
            pattern=r"^[A-Za-z0-9_-]+$",
        ),
    ],
    identity: Identity = Depends(require_candidate_manager),
    db_path: Path = Depends(get_db_path),
):
    ensure_election_permission(identity, election_id)

    try:
        return save_candidate_deactivation(
            candidate_id,
            election_id,
            db_path,
        )

    except CandidateNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found in this election",
        )

    except ElectionLockedError:
        raise HTTPException(
            status_code=409,
            detail="Candidate changes require a draft election",
        )    