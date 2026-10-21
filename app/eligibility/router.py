"""Owner: Ved. Replace placeholders with reviewed implementation."""
from fastapi import APIRouter
from app.shared.placeholders import unfinished

router = APIRouter(prefix="/eligibility", tags=["eligibility"])

@router.post("/enrol")
def operation_1():
    unfinished("eligibility")

@router.post("/check")
def operation_2():
    unfinished("eligibility")

@router.post("/authorizations")
def operation_3():
    unfinished("eligibility")
