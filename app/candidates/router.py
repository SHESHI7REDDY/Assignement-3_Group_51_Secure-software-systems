"""Owner: Sashi. Replace placeholders with reviewed implementation."""
from fastapi import APIRouter
from app.shared.placeholders import unfinished

router = APIRouter(prefix="/candidates", tags=["candidates"])

@router.get("")
def operation_1():
    unfinished("candidates")

@router.post("")
def operation_2():
    unfinished("candidates")

@router.patch("/{candidate_id}")
def operation_3(candidate_id: str):
    unfinished("candidates")
