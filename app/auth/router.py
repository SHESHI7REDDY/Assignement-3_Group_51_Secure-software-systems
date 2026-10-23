
"""Authentication REST API endpoints."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials,
)

from app.auth.schemas import (
    RegisterRequest,
    UserResponse,
    SessionLoginRequest,
    SessionTokenResponse,
)
from app.auth.service import (
    register_user,
    login_with_session,
)
from app.auth.sessions import (
    validate_session,
    invalidate_session,
)
from app.auth.repository import get_user_by_id


router = APIRouter(prefix="/auth", tags=["auth"])

bearer_scheme = HTTPBearer(auto_error=False)


def require_authenticated_session(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> tuple[int, str]:
    """Require a valid bearer session token."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    user_id = validate_session(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id, token


SessionDependency = Annotated[
    tuple[int, str],
    Depends(require_authenticated_session),
]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(data: RegisterRequest):
    """Register a new user."""
    return register_user(data)


@router.post(
    "/login",
    response_model=SessionTokenResponse,
)
def login(data: SessionLoginRequest):
    """Authenticate and create a session."""
    return login_with_session(
        username=data.username,
        password=data.password,
        mfa_code=data.mfa_code,
    )


@router.get(
    "/verify",
    response_model=UserResponse,
)
def verify(session: SessionDependency):
    """Return the authenticated user's public information."""

    user_id, _ = session
    user = get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )

    return user


@router.post("/logout")
def logout(session: SessionDependency):
    """Revoke the current session."""

    _, token = session

    if not invalidate_session(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session already invalid",
        )

    return {"message": "Logged out successfully"}
