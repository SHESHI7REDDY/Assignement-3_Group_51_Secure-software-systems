"""Owner: Akshit. Replace placeholders with reviewed implementation."""
from fastapi import APIRouter
from app.shared.placeholders import unfinished

router = APIRouter(prefix="/ballots", tags=["ballot"])

@router.get("/template")
def operation_1():
    unfinished("ballot")

@router.post("")
def operation_2():
    unfinished("ballot")
