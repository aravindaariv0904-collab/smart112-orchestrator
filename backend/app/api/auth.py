import logging
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.core.security import (
    authenticate_user,
    is_authorized_dispatcher,
    verify_dispatcher_token,
)

logger = logging.getLogger("smart112.api.auth")
router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=100)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    callsign: str
    role: str
    permissions: List[str]


@router.post("/login", response_model=LoginResponse)
def login_dispatcher(payload: LoginRequest):
    """
    Authenticate emergency dispatchers, supervisors, and commanders.
    Returns a tamper-evident bearer token with backend-enforced RBAC permissions.
    """
    auth = authenticate_user(payload.username, payload.password)
    if not auth:
        logger.warning("Failed login attempt for username '%s'", payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid dispatcher credentials. Access denied.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info("Dispatcher '%s' authenticated successfully (role: %s)", auth["callsign"], auth["role"])
    return {
        "access_token": auth["token"],
        "token_type": "bearer",
        "callsign": auth["callsign"],
        "role": auth["role"],
        "permissions": auth["permissions"],
    }


@router.get("/verify")
def verify_session(
    authorization: Optional[str] = Header(None),
    x_dispatcher_token: Optional[str] = Header(None, alias="X-Dispatcher-Token"),
):
    """Verify an active dispatcher session token or API key."""
    token = x_dispatcher_token or authorization
    if not token or not verify_dispatcher_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired dispatcher session token.",
        )
    return {"status": "authenticated", "valid": True}
