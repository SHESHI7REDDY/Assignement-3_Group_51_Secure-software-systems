
"""Authentication REST API endpoints with RBAC and auditing."""

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
from app.auth.audit import (
    record_security_event,
    get_recent_audit_events,
)


router = APIRouter(prefix="/auth", tags=["auth"])

bearer_scheme = HTTPBearer(auto_error=False)


def require_authenticated_session(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> tuple[int, str]:
    """Require a valid session token."""

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


def require_admin(
    session: SessionDependency,
) -> dict:
    """Allow access only to users with the admin role."""

    user_id, _ = session
    user = get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid account",
        )

    if user["role"] != "admin":
        record_security_event(
            "ADMIN_ACCESS_DENIED",
            user_id,
        )

        raise HTTPException(
            status_code=403,
            detail="Administrator access required",
        )

    record_security_event(
        "ADMIN_ACCESS_GRANTED",
        user_id,
    )

    return user


AdminDependency = Annotated[
    dict,
    Depends(require_admin),
]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(data: RegisterRequest):
    """Register a new voter account."""

    user = register_user(data)

    record_security_event(
        "USER_REGISTERED",
        user["id"],
    )

    return user


@router.post(
    "/login",
    response_model=SessionTokenResponse,
)
def login(data: SessionLoginRequest):
    """Authenticate a user and record the outcome."""

    try:
        result = login_with_session(
            username=data.username,
            password=data.password,
            mfa_code=data.mfa_code,
        )

    except HTTPException:
        record_security_event("LOGIN_FAILED")
        raise

    record_security_event("LOGIN_SUCCESS")

    return result


@router.get(
    "/verify",
    response_model=UserResponse,
)
def verify(session: SessionDependency):
    """Verify a session and return public account details."""

    user_id, _ = session
    user = get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User no longer exists",
        )

    record_security_event(
        "SESSION_VERIFIED",
        user_id,
    )

    return user


@router.post("/logout")
def logout(session: SessionDependency):
    """Revoke the current authenticated session."""

    user_id, token = session

    if not invalidate_session(token):
        raise HTTPException(
            status_code=401,
            detail="Session already invalid",
        )

    record_security_event(
        "LOGOUT_SUCCESS",
        user_id,
    )

    return {"message": "Logged out successfully"}


@router.get("/admin/audit")
def admin_audit(
    admin: AdminDependency,
):
    """Provide recent audit events to administrators only."""

    return {
        "events": get_recent_audit_events(),
    }
