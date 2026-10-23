"""Owner: Ved. Eligibility & one-vote rule REST API (ELIG-01 to ELIG-04).

Every route needs a verified bearer token (security.get_principal). Roles:
voter (own record only), officer (AEC staff), service (Ballot module).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from . import audit, service
from .config import Settings, get_settings
from .repository import connect, init_db
from .schemas import (VOTER_ID, AddressUpdate, AuthoriseRequest, EnrolRequest, RedeemRequest,
                      VoterRef)
from .security import Principal, ensure_self_or_officer, require_roles

router = APIRouter(prefix="/eligibility", tags=["eligibility"])
VoterIdPath = Annotated[str, Path(pattern=VOTER_ID)]


def get_conn(settings: Settings = Depends(get_settings)):
    init_db(settings.db_path)  # CREATE TABLE IF NOT EXISTS - safe to repeat
    conn = connect(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


# ---------- Enrolment ----------
@router.post("/enrol", status_code=201)
def enrol(body: EnrolRequest, p: Principal = Depends(require_roles("voter", "officer")),
          conn=Depends(get_conn), settings: Settings = Depends(get_settings)):
    ensure_self_or_officer(p, body.voter_id)
    try:
        st = service.enrol(conn, settings, p, body.model_dump())
    except ValueError:
        raise HTTPException(409, "Already enrolled")
    return {"voter_id": body.voter_id, "enrolment_status": st}


@router.get("/status/{voter_id}")
def enrolment_status(voter_id: VoterIdPath, p: Principal = Depends(require_roles("voter", "officer")),
                     conn=Depends(get_conn)):
    ensure_self_or_officer(p, voter_id)
    row = conn.execute("SELECT enrolment_status, state, division FROM electors WHERE voter_id = ?",
                       (voter_id,)).fetchone()
    if not row:
        return {"voter_id": voter_id, "enrolment_status": "NOT_ENROLLED"}
    return {"voter_id": voter_id, **dict(row)}


@router.post("/enrolments/{voter_id}/approve")
def approve(voter_id: VoterIdPath, p: Principal = Depends(require_roles("officer")),
            conn=Depends(get_conn), settings: Settings = Depends(get_settings)):
    try:
        service.approve(conn, settings, p, voter_id)
    except service.NotFound:
        raise HTTPException(404, "No pending enrolment")
    return {"voter_id": voter_id, "enrolment_status": "ENROLLED"}


@router.patch("/electors/{voter_id}/address")
def update_address(voter_id: VoterIdPath, body: AddressUpdate,
                   p: Principal = Depends(require_roles("voter", "officer")),
                   conn=Depends(get_conn), settings: Settings = Depends(get_settings)):
    ensure_self_or_officer(p, voter_id)
    try:
        service.update_address(conn, settings, p, voter_id, body.address, body.division)
    except service.NotFound:
        raise HTTPException(404, "Elector not found")
    return {"voter_id": voter_id, "updated": True}


# ---------- Eligibility + one-vote rule ----------
@router.post("/check")
def check(body: VoterRef, p: Principal = Depends(require_roles("voter", "officer")),
          conn=Depends(get_conn), settings: Settings = Depends(get_settings)):
    ensure_self_or_officer(p, body.voter_id)
    d = service.check(conn, settings, p, body.voter_id)
    return {"voter_id": body.voter_id, "election_id": settings.election_id,
            "eligible": d.eligible, "reason": d.reason}


@router.post("/authorizations", status_code=201)
def authorise(body: AuthoriseRequest, p: Principal = Depends(require_roles("voter", "officer")),
              conn=Depends(get_conn), settings: Settings = Depends(get_settings)):
    ensure_self_or_officer(p, body.voter_id)
    if not settings.mock_auth:
        raise HTTPException(409, "Submit through /ballots/submit so the vote and ballot are saved together")
    if p.role == "voter" and body.channel != "ONLINE":
        raise HTTPException(403, "Voters may only self-authorise for online voting")
    try:
        return service.authorise_to_vote(conn, settings, p, body.voter_id, body.channel)
    except service.AlreadyVoted:
        raise HTTPException(status.HTTP_409_CONFLICT, "ALREADY_VOTED")
    except service.NotEligible as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, e.reason)


@router.post("/authorizations/redeem")
def redeem(body: RedeemRequest, p: Principal = Depends(require_roles("service")),
           conn=Depends(get_conn), settings: Settings = Depends(get_settings)):
    result = service.redeem_token(conn, settings, p, body.ballot_token)
    if not result:
        raise HTTPException(409, "Token invalid, expired or already used")
    return {"valid": True, **result}


# ---------- Audit ----------
@router.get("/audit/verify")
def verify_audit(p: Principal = Depends(require_roles("officer")), conn=Depends(get_conn)):
    return audit.verify_chain(conn)


@router.get("/audit/recent")
def recent_audit(p: Principal = Depends(require_roles("officer")), conn=Depends(get_conn)):
    rows = conn.execute("SELECT seq, ts, actor_role, action, subject_ref, outcome, entry_hash "
                        "FROM audit_log ORDER BY seq DESC LIMIT 15").fetchall()
    return [dict(r) for r in rows]
