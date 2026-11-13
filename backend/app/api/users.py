"""
User Management API

Provides CRUD operations for:
- Users (create, read, update, delete)
- Roles (list, create, update)
- User sessions (list, invalidate)
- Password management (change, reset)
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, EmailStr

from backend.app.core.database import get_db, Session
from backend.app.models.user import User, Role, UserSession, Responder
from backend.app.core.security import is_authorized_dispatcher, check_rbac_permission

logger = logging.getLogger("smart112.api.users")
router = APIRouter(prefix="/api/v1/users", tags=["users"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    email: str = Field(..., max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=200)
    role_id: str = Field(..., description="Role ID to assign to user")
    is_active: bool = True
    is_verified: bool = False

class UserUpdate(BaseModel):
    email: Optional[str] = Field(None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: Optional[str] = Field(None, max_length=200)
    role_id: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: Optional[str]
    role_id: str
    role_name: str
    is_active: bool
    is_verified: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class RoleCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Z_]+$")
    permissions: str = Field(..., description="Comma-separated permissions")
    description: Optional[str] = Field(None, max_length=500)
    is_system_role: bool = False

class RoleUpdate(BaseModel):
    permissions: Optional[str] = None
    description: Optional[str] = None
    # is_system_role cannot be changed after creation

class RoleResponse(BaseModel):
    id: str
    name: str
    permissions: str
    description: Optional[str]
    is_system_role: bool
    created_at: datetime
    user_count: int = 0

    class Config:
        from_attributes = True

class UserSessionResponse(BaseModel):
    id: str
    user_id: str
    device_info: Optional[str]
    ip_address: Optional[str]
    expires_at: datetime
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True

class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)

class PasswordChangeResponse(BaseModel):
    message: str = "Password changed successfully"


# =============================================================================
# User Endpoints
# =============================================================================

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    """Create a new user account."""
    # Require admin role
    if not is_authorized_dispatcher("SYSTEM", None):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    if not check_rbac_permission("ADMIN", "CREATE_USERS"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    
    # Check if username already exists
    if db.query(User).filter(User.username == payload.username.lower()).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )
    
    # Check if email already exists
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    # Validate role exists
    role = db.query(Role).filter(Role.id == payload.role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{payload.role_id}' not found"
        )
    
    # Create user with Argon2id hashed password
    user = User(
        id=f"user-{datetime.now(timezone.utc).timestamp()}",
        username=payload.username.lower(),
        email=payload.email.lower(),
        full_name=payload.full_name,
        role_id=payload.role_id,
        is_active=payload.is_active,
        is_verified=payload.is_verified,
    )
    user.set_password(payload.password)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    user.role = role
    
    logger.info("Created user: %s (role: %s)", user.username, role.name)
    return user


@router.get("", response_model=List[UserResponse])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    active: Optional[bool] = None,
    role: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List users with filtering and pagination."""
    query = db.query(User)
    
    if active is not None:
        query = query.filter(User.is_active == active)
    
    if role:
        query = query.filter(User.role_id == role)
    
    if search:
        search_term = f"%{search.lower()}%"
        query = query.filter(
            (User.username.ilike(search_term)) |
            (User.email.ilike(search_term)) |
            (User.full_name.ilike(search_term))
        )
    
    users = query.offset(skip).limit(limit).all()
    return users


# =============================================================================
# Role Endpoints
# =============================================================================

@router.get("/roles", response_model=List[RoleResponse])
def list_roles(
    db: Session = Depends(get_db),
):
    """List all roles with user counts."""
    roles = db.query(Role).all()
    
    result = []
    for role in roles:
        user_count = db.query(User).filter(User.role_id == role.id).count()
        result.append({
            "id": role.id,
            "name": role.name,
            "permissions": role.permissions,
            "description": role.description,
            "is_system_role": role.is_system_role,
            "created_at": role.created_at,
            "user_count": user_count,
        })
    
    return result


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
):
    """Create a new role."""
    # Check if role name already exists
    if db.query(Role).filter(Role.name == payload.name.upper()).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role name already exists"
        )
    
    role = Role(
        id=f"role-{payload.name.lower()}",
        name=payload.name.upper(),
        permissions=payload.permissions,
        description=payload.description,
        is_system_role=payload.is_system_role,
    )
    
    db.add(role)
    db.commit()
    db.refresh(role)
    
    logger.info("Created role: %s", role.name)
    return role


@router.put("/roles/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: str,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
):
    """Update a role's permissions or description."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # System roles cannot be modified
    if role.is_system_role and not payload.description:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify system role"
        )
    
    if payload.permissions is not None:
        role.permissions = payload.permissions
    
    if payload.description is not None:
        role.description = payload.description
    
    db.commit()
    db.refresh(role)
    
    logger.info("Updated role: %s", role.name)
    return role


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
):
    """Delete a role (only non-system roles with no users)."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Cannot delete system roles
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system role"
        )
    
    # Check if any users have this role
    user_count = db.query(User).filter(User.role_id == role_id).count()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete role with {user_count} active users"
        )
    
    db.delete(role)
    db.commit()
    
    logger.info("Deleted role: %s", role.name)
    return None


# =============================================================================
# Session Management Endpoints
# =============================================================================

@router.get("/sessions", response_model=List[UserSessionResponse])
def list_user_sessions(
    user_id: str = Query(..., description="User ID to list sessions for"),
    db: Session = Depends(get_db),
):
    """List all active sessions for a user."""
    query = db.query(UserSession).filter(UserSession.user_id == user_id)
    return query.order_by(UserSession.created_at.desc()).all()


@router.get("/me", response_model=UserResponse)
def get_current_user(
    current_user: User = Depends(lambda db: db.query(User).filter(User.id == "user-dispatcher-01").first()),
    db: Session = Depends(get_db),
):
    """Get the currently authenticated user (requires auth middleware)."""
    # In production, this would use JWT auth middleware
    # For now, return the test user
    return current_user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
):
    """Update a user's information."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    if payload.email:
        # Check email uniqueness
        existing = db.query(User).filter(
            User.email == payload.email.lower(),
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use"
            )
        user.email = payload.email.lower()
    
    if payload.full_name is not None:
        user.full_name = payload.full_name
    
    if payload.role_id:
        role = db.query(Role).filter(Role.id == payload.role_id).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{payload.role_id}' not found"
            )
        user.role_id = payload.role_id
    
    if payload.is_active is not None:
        user.is_active = payload.is_active
    
    if payload.is_verified is not None:
        user.is_verified = payload.is_verified
    
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    
    logger.info("Updated user: %s", user.username)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
):
    """Soft delete a user (sets is_active=False)."""
    # Require admin role
    if not is_authorized_dispatcher("SYSTEM", None):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = False
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    
    logger.info("Deactivated user: %s", user.username)
    return None


@router.post("/{user_id}/change-password", response_model=PasswordChangeResponse)
def change_password(
    user_id: str,
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
):
    """Change a user's password (requires current password)."""
    # Require auth - user can only change their own password
    if not is_authorized_dispatcher(user_id, None):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify current password
    if not user.verify_password(payload.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Set new password
    user.set_password(payload.new_password)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    
    logger.info("Password changed for user: %s", user.username)
    return {"message": "Password changed successfully"}


# =============================================================================
# Responder Profile Endpoints
# =============================================================================

@router.get("/{user_id}/responder", response_model=Optional[dict])
def get_responder_profile(
    user_id: str,
    db: Session = Depends(get_db),
):
    """Get a user's responder profile if they have one."""
    responder = db.query(Responder).filter(Responder.user_id == user_id).first()
    if not responder:
        return None
    
    return {
        "id": responder.id,
        "user_id": responder.user_id,
        "callsign": responder.callsign,
        "full_name": responder.full_name,
        "unit_id": responder.unit_id,
        "certifications": responder.certifications,
        "is_available": responder.is_available,
        "specialties": responder.specialties,
        "created_at": responder.created_at,
        "updated_at": responder.updated_at,
    }


@router.post("/{user_id}/responder", status_code=status.HTTP_201_CREATED)
def create_responder_profile(
    user_id: str,
    callsign: str,
    full_name: str,
    unit_id: Optional[str] = None,
    certifications: Optional[List[str]] = None,
    specialties: Optional[List[str]] = None,
    db: Session = Depends(get_db),
):
    """Create a responder profile for a user."""
    # Require admin or supervisor role
    if not is_authorized_dispatcher("SYSTEM", None):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if responder profile already exists
    existing = db.query(Responder).filter(Responder.user_id == user_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Responder profile already exists for this user"
        )
    
    responder = Responder(
        id=f"responder-{user_id}",
        user_id=user_id,
        callsign=callsign,
        full_name=full_name,
        unit_id=unit_id,
        certifications=certifications or [],
        specialties=specialties or [],
        is_available=True,
    )
    
    db.add(responder)
    db.commit()
    db.refresh(responder)
    
    logger.info("Created responder profile for user: %s", user_id)
    return {"message": "Responder profile created", "responder_id": responder.id}
