
"""Authentication REST API endpoints."""

from fastapi import APIRouter, status

from app.auth.schemas import RegisterRequest, UserResponse
from app.auth.service import register_user
from app.shared.placeholders import unfinished

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(data: RegisterRequest):
    return register_user(data)


@router.post("/login")
def login():
    unfinished("auth")


@router.post("/logout")
def logout():
    unfinished("auth")


@router.get("/verify")
def verify():
    unfinished("auth")
