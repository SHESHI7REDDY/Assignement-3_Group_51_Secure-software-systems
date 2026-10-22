"""Owner: Moinul. Replace placeholders with reviewed implementation."""
from fastapi import APIRouter
from app.shared.placeholders import unfinished

router = APIRouter(prefix="/results", tags=["results"])

@router.post("/count")
def operation_1():
    unfinished("results")

@router.get("/{election_id}")
def operation_2(election_id: str):
    unfinished("results")

@router.post("/{election_id}/publish")
def operation_3(election_id: str):
    unfinished("results")


from app.results.audit_api import router as audit_router
router.include_router(audit_router)
