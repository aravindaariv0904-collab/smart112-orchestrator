"""User and authentication models with Argon2id support."""

import argon2
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class User(Base):
    """System user with RBAC role assignment."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(String(36), ForeignKey("roles.id"), nullable=False, index=True)
    full_name = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    role = relationship("Role", back_populates="users")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    responder_profile = relationship("Responder", back_populates="user", uselist=False, cascade="all, delete-orphan")

    @property
    def role_name(self) -> str:
        return self.role.name if self.role else ""

    def set_password(self, password: str) -> None:
        """Hash password using Argon2id."""
        hasher = argon2.PasswordHasher(
            time_cost=3,
            memory_cost=64 * 1024,
            parallelism=4,
            hash_len=32,
            type=argon2.Type.ID
        )
        self.password_hash = hasher.hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify password against Argon2id hash."""
        try:
            hasher = argon2.PasswordHasher()
            return hasher.verify(self.password_hash, password)
        except Exception:
            return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "role_id": self.role_id,
            "role_name": self.role.name if self.role else None,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Role(Base):
    """RBAC role with permission set."""

    __tablename__ = "roles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    permissions = Column(String(1000), default="", nullable=False)  # Comma-separated permission list
    is_system_role = Column(Boolean, default=False, nullable=False)  # System roles cannot be deleted
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    users = relationship("User", back_populates="role")

    def get_permissions(self) -> list[str]:
        return [p.strip() for p in self.permissions.split(",") if p.strip()]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": self.get_permissions(),
            "is_system_role": self.is_system_role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserSession(Base):
    """Authenticated user session with token expiration."""

    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(500), unique=True, nullable=False, index=True)
    refresh_token = Column(String(500), unique=True, nullable=False, index=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=False)
    refresh_token_expires_at = Column(DateTime(timezone=True), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_activity_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="sessions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "token_expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Responder(Base):
    """Emergency responder profile linked to a user."""

    __tablename__ = "responders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False, index=True)
    callsign = Column(String(50), unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=False)
    rank = Column(String(50), nullable=True)
    unit_id = Column(String(36), ForeignKey("emergency_units.id"), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    certifications = Column(String(500), default="", nullable=False)  # Comma-separated
    is_available = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="responder_profile")
    unit = relationship("EmergencyUnit", back_populates="assigned_responder", foreign_keys="[Responder.unit_id]")
    gps_devices = relationship("GPSDevice", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "callsign": self.callsign,
            "full_name": self.full_name,
            "rank": self.rank,
            "unit_id": self.unit_id,
            "phone": self.phone,
            "email": self.email,
            "certifications": self.get_certifications(),
            "is_available": self.is_available,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def get_certifications(self) -> list[str]:
        return [c.strip() for c in self.certifications.split(",") if c.strip()]
