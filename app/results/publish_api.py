"""Administrator-only publication endpoint for the local fictional prototype.

The local token is a mock authorization mechanism, not production identity.
"""
from fastapi import APIRouter, Header, HTTPException
from app.results.audit_api import _require_admin
from app.results.audit import verify_audit, append_event
from app.results.repository import publish_count, get_count, ResultStorageError

router = APIRouter(tags=["results-publication"])


@router.post("/{election_id}/publish")
def publish_election_result(election_id: str, x_results_admin_token: str | None = Header(default=None)):
    key, db = _require_admin(x_results_admin_token)
    if not verify_audit(key, db):
        raise HTTPException(409, "Audit integrity verification failed")
    existing = get_count(election_id, db)
    if existing is None:
        raise HTTPException(404, "Election results not found")
    if existing["status"] != "counted":
        raise HTTPException(409, "Election results already published")
    try:
        saved = publish_count(election_id, db)
    except ResultStorageError as exc:
        raise HTTPException(409, str(exc)) from exc
    append_event(election_id, "RESULT_PUBLISHED", "local-demo-admin", "success", key, db)
    return saved
