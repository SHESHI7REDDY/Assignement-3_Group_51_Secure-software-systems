
"""Authentication REST API endpoints."""

from fastapi import APIRouter, status

from app.auth.schemas import RegisterRequest, LoginRequest, UserResponse
from app.auth.service import register_user, authenticate_user
from app.shared.placeholders import unfinished

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(data: RegisterRequest):
    return register_user(data)


@router.post("/login", response_model=UserResponse)
def login(data: LoginRequest):
    return authenticate_user(data)


@router.post("/logout")
def logout():
    unfinished("auth")


@router.get("/verify")
def verify():
    unfinished("auth")
