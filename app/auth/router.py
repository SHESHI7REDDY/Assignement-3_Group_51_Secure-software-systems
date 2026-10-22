
"""Authentication REST API endpoints."""

from fastapi import APIRouter, status

from app.auth.schemas import RegisterRequest, LoginRequest, UserResponse
from app.auth.service import register_user, authenticate_user
from app.shared.placeholders import unfinished
from app.auth.schemas import (
    SessionLoginRequest,
    SessionTokenResponse,
)
from app.auth.service import login_with_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(data: RegisterRequest):
    return register_user(data)



@router.post(
    "/login",
    response_model=SessionTokenResponse,
)
def login(data: SessionLoginRequest):
    return login_with_session(
        username=data.username,
        password=data.password,
        mfa_code=data.mfa_code,
    )


@router.post("/logout")
def logout():
    unfinished("auth")


@router.get("/verify")
def verify():
    unfinished("auth")
