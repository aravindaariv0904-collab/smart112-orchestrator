"""Secure evidence management for multimedia and documents."""

import os
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class Evidence(Base):
    """Secure evidence record with access control."""

    __tablename__ = "evidence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    evidence_id = Column(String(50), unique=True, nullable=False, index=True)  # Evidence reference ID
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False, index=True)
    case_number = Column(String(50), nullable=True)  # Related case/file number
    evidence_type = Column(String(50), nullable=False)  # audio, image, video, document, telemetry, transcription
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # File metadata
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    duration_seconds = Column(Float, nullable=True)
    width_pixels = Column(Integer, nullable=True)  # For images/video
    height_pixels = Column(Integer, nullable=True)  # For images/video
    frame_count = Column(Integer, nullable=True)  # For video
    
    # Storage
    storage_path = Column(String(500), nullable=False)  # Relative path in secure storage
    storage_bucket = Column(String(100), nullable=True)  # S3 bucket, etc.
    storage_key = Column(String(500), nullable=True)  # Object key
    checksum = Column(String(64), nullable=True)  # SHA-256
    encryption_algorithm = Column(String(50), nullable=True)  # aes-256-gcm, etc.
    is_encrypted = Column(Boolean, default=False, nullable=False)
    
    # Classification
    classification = Column(String(50), default="standard", nullable=False)  # standard, sensitive, restricted, confidential
    access_level = Column(String(50), default="dispatch", nullable=False)  # public, dispatch, responder, medical, admin
    
    # Chain of custody
    submitted_by = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    accessed_by = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    modified_by = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    modified_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deletion_reason = Column(Text, nullable=True)
    
    # Verification
    is_verified = Column(Boolean, default=False, nullable=False)  # Verified authentic
    verified_by = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_notes = Column(Text, nullable=True)
    
    # Legal
    retention_policy = Column(String(50), default="standard", nullable=False)  # standard, extended, indefinite
    legal_hold = Column(Boolean, default=False, nullable=False)
    legal_hold_reason = Column(Text, nullable=True)
    
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    incident_rel = relationship("Incident", foreign_keys="[Evidence.incident_id]")
    submitter = relationship("User", foreign_keys=[submitted_by])
    accessed_by_user = relationship("User", foreign_keys=[accessed_by])
    modified_by_user = relationship("User", foreign_keys=[modified_by])
    deleter = relationship("User", foreign_keys=[deleted_by])
    verifier = relationship("User", foreign_keys=[verified_by])

    def to_dict(self, include_sensitive: bool = False) -> dict:
        data = {
            "id": self.id,
            "evidence_id": self.evidence_id,
            "incident_id": self.incident_id,
            "evidence_type": self.evidence_type,
            "title": self.title,
            "description": self.description,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "storage_path": self.storage_path if include_sensitive else None,
            "is_encrypted": self.is_encrypted,
            "classification": self.classification,
            "access_level": self.access_level,
            "submitted_by": self.submitted_by,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "is_verified": self.is_verified,
            "is_deleted": self.is_deleted,
            "retention_policy": self.retention_policy,
            "legal_hold": self.legal_hold,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_sensitive:
            data.update({
                "original_filename": self.original_filename,
                "duration_seconds": self.duration_seconds,
                "width_pixels": self.width_pixels,
                "height_pixels": self.height_pixels,
                "storage_bucket": self.storage_bucket,
                "storage_key": self.storage_key,
                "checksum": self.checksum,
                "encryption_algorithm": self.encryption_algorithm,
            })
        return data

    def can_access(self, user_role: str, purpose: str = "view") -> bool:
        """Check if user with given role can access this evidence."""
        access_map = {
            "public": ["admin"],
            "dispatch": ["admin", "supervisor", "dispatcher"],
            "responder": ["admin", "supervisor", "dispatcher", "responder"],
            "medical": ["admin", "supervisor", "dispatcher", "responder", "medical_coordinator"],
            "confidential": ["admin"],
        }
        allowed_roles = access_map.get(self.access_level, ["admin"])
        return user_role in allowed_roles


class EvidenceAccessLog(Base):
    """Chain of custody access log for evidence."""

    __tablename__ = "evidence_access_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    evidence_id = Column(String(36), ForeignKey("evidence.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(50), nullable=False)  # view, download, copy, share, modify, delete
    access_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    reason = Column(Text, nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    evidence = relationship("Evidence", backref="access_logs")
    user = relationship("User", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approved_by])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "evidence_id": self.evidence_id,
            "user_id": self.user_id,
            "action": self.action,
            "access_time": self.access_time.isoformat() if self.access_time else None,
            "ip_address": self.ip_address,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Document(Base):
    """Document evidence (PDFs, forms, reports)."""

    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    evidence_id = Column(String(36), ForeignKey("evidence.id"), unique=True, nullable=False, index=True)
    document_type = Column(String(50), nullable=False)  # report, form, certificate, letter, invoice, other
    document_subtype = Column(String(50), nullable=True)  # incident_report, medical_report, police_report, etc.
    page_count = Column(Integer, nullable=True)
    author = Column(String(100), nullable=True)
    created_date = Column(DateTime(timezone=True), nullable=True)
    
    # Indexing for search
    search_text = Column(Text, nullable=True)  # Extracted text for full-text search
    tags = Column(String(500), default="", nullable=False)  # Comma-separated tags
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    evidence = relationship("Evidence", backref="document_data")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "evidence_id": self.evidence_id,
            "document_type": self.document_type,
            "document_subtype": self.document_subtype,
            "page_count": self.page_count,
            "author": self.author,
            "tags": self.get_tags(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def get_tags(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]


# Update User model import to avoid circular imports
from backend.app.models.user import User
