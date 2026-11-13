import logging
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException, status, Request, Response
from pydantic import BaseModel, Field

from backend.app.core.security import (
    authenticate_user,
    is_authorized_dispatcher,
    verify_dispatcher_token,
    verify_token,
    create_access_token,
    create_refresh_token,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
)
from backend.app.core.rate_limiter import (
    rate_limiter,
    get_client_ip,
    get_auth_rate_key,
    clear_rate_limit,
)

logger = logging.getLogger("smart112.api.auth")
router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=100)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    callsign: str
    role: str
    permissions: List[str]


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    callsign: str
    role: str


@router.post("/login", response_model=LoginResponse)
async def login_dispatcher(payload: LoginRequest, request: Request, response: Response):
    """
    Authenticate emergency dispatchers, supervisors, and commanders.
    Returns JWT access and refresh tokens with backend-enforced RBAC permissions.
    
    Rate limited to prevent brute force attacks.
    """
    rate_key = get_auth_rate_key(request, payload.username)
    
    allowed, info = await rate_limiter.check_rate_limit(rate_key)
    if not allowed:
        logger.warning(
            "Rate limit exceeded for login attempt for user %s",
            payload.username
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Too many login attempts. Please try again later.",
            headers={
                "Retry-After": str(max(1, int(info["block_duration"]))),
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": "0",
            },
        )
    
    auth = authenticate_user(payload.username, payload.password)
    if not auth:
        logger.warning("Failed login attempt for username '%s'", payload.username)
        # Add a small delay to slow down brute force (optional)
        # time.sleep(0.5)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid dispatcher credentials. Access denied.",
            headers={
                "WWW-Authenticate": "Bearer",
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": str(info["remaining"]),
            },
        )

    # Clear rate limit on successful auth
    clear_rate_limit(rate_key)
    
    response.headers["X-RateLimit-Limit"] = str(info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    
    # Create JWT tokens with expiration
    access_token = create_access_token(auth["callsign"], auth["role"])
    refresh_token = create_refresh_token(auth["callsign"], auth["role"])
    
    logger.info("Dispatcher '%s' authenticated successfully (role: %s)", auth["callsign"], auth["role"])
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_token": refresh_token,
        "callsign": auth["callsign"],
        "role": auth["role"],
        "permissions": auth["permissions"],
    }


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_access_token(payload: RefreshRequest, request: Request, response: Response):
    """
    Refresh an expired access token using a valid refresh token.
    Returns a new access token with fresh expiration.
    
    Rate limited to prevent abuse.
    """
    rate_key = request.url.path
    
    allowed, info = await rate_limiter.check_rate_limit(rate_key)
    if not allowed:
        logger.warning("Rate limit exceeded for token refresh")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Too many refresh requests. Please try again later.",
            headers={
                "Retry-After": str(max(1, int(info["block_duration"]))),
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": "0",
            },
        )
    
    response.headers["X-RateLimit-Limit"] = str(info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    
    # Verify the refresh token
    payload_data = verify_token(payload.refresh_token)
    if not payload_data:
        logger.warning("Invalid refresh token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
            headers={
                "WWW-Authenticate": "Bearer",
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": str(info["remaining"]),
            },
        )
    
    # Ensure it's a refresh token type
    if payload_data.get("type") != "refresh":
        logger.warning("Token type mismatch: expected refresh, got %s", payload_data.get("type"))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Use a refresh token.",
            headers={
                "WWW-Authenticate": "Bearer",
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": str(info["remaining"]),
            },
        )
    
    # Extract subject and role from the refresh token
    subject = payload_data.get("sub")
    role = payload_data.get("role")
    
    if not subject or not role:
        logger.warning("Refresh token missing subject or role from %s", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload.",
            headers={
                "WWW-Authenticate": "Bearer",
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": str(info["remaining"]),
            },
        )
    
    # Create new access token
    new_access_token = create_access_token(subject, role)
    
    logger.info("Access token refreshed for '%s' (role: %s)", subject, role)
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "callsign": subject,
        "role": role,
    }


@router.get("/verify")
async def verify_session(
    authorization: Optional[str] = Header(None),
    x_dispatcher_token: Optional[str] = Header(None, alias="X-Dispatcher-Token"),
    request: Request = None,
):
    """Verify an active dispatcher session token or API key."""
    token = x_dispatcher_token or authorization
    
    # Rate limiting check for verify endpoint - use URL path
    if request:
        rate_key = request.url.path
        allowed, info = await rate_limiter.check_rate_limit(rate_key)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many verification requests. Please try again later.",
                headers={
                    "Retry-After": str(int(info["block_duration"])),
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                },
            )
    
    # Check JWT token first
    if token and token.startswith("Bearer "):
        jwt_token = token[7:]
        payload = verify_token(jwt_token)
        if payload and payload.get("type") == "access":
            return {
                "status": "authenticated",
                "valid": True,
                "callsign": payload.get("sub"),
                "role": payload.get("role"),
                "expires_at": payload.get("exp")
            }
    
    # Fall back to legacy API key verification
    if token and verify_dispatcher_token(token):
        return {"status": "authenticated", "valid": True, "auth_method": "legacy_api_key"}
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired dispatcher session token.",
    )
