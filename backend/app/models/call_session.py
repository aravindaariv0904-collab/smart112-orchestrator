"""Emergency call session management."""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Float, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class CallSession(Base):
    """Emergency call session with audio and transcription tracking."""

    __tablename__ = "call_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String(50), unique=True, nullable=False, index=True)  # Human-readable session ID
    caller_phone = Column(String(50), nullable=True)
    caller_name = Column(String(100), nullable=True)
    language_detected = Column(String(10), default="en", nullable=False)  # en, te, hi, ta, kn, ml
    language_confidence = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String(255), nullable=True)
    location_source = Column(String(50), default="manual", nullable=False)  # manual, gps, caller, network
    location_confidence = Column(Float, nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    audio_file_id = Column(String(36), ForeignKey("audio_files.id"), nullable=True, index=True)
    transcription_id = Column(String(36), ForeignKey("transcriptions.id"), nullable=True, index=True)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=True, index=True)
    is_simulated = Column(Boolean, default=False, nullable=False)  # Flag for test/simulated calls
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    audio_file = relationship("AudioFile", back_populates="call_session", foreign_keys="[AudioFile.call_session_id]")
    transcription = relationship("Transcription", back_populates="call_session", foreign_keys="[Transcription.call_session_id]")
    incident = relationship("Incident", back_populates="call_session", foreign_keys="[CallSession.incident_id]")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "caller_phone": self.caller_phone,
            "caller_name": self.caller_name,
            "language_detected": self.language_detected,
            "language_confidence": self.language_confidence,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "address": self.address,
            "location_source": self.location_source,
            "location_confidence": self.location_confidence,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "incident_id": self.incident_id,
            "is_simulated": self.is_simulated,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Transcription(Base):
    """Stored transcription with confidence scores per segment."""

    __tablename__ = "transcriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    call_session_id = Column(String(36), ForeignKey("call_sessions.id"), nullable=False, index=True)
    raw_transcript = Column(Text, nullable=False)
    detected_language = Column(String(10), default="en", nullable=False)
    language_probability = Column(Float, nullable=True)
    overall_confidence = Column(Float, nullable=True)
    stt_engine = Column(String(50), nullable=False)  # whisper, gcloud, aws, etc.
    stt_status = Column(String(50), nullable=False)  # SUCCESS, PARTIAL, FAILED, NO_SPEECH
    processing_duration_ms = Column(Integer, nullable=True)
    is_verbatim = Column(Boolean, default=True, nullable=False)  # True = raw transcription, False = cleaned
    ai_summary = Column(Text, nullable=True)  # AI-generated summary
    ai_summary_confidence = Column(Float, nullable=True)
    segments = Column(Text, nullable=True)  # JSON array of segments with timestamps and confidence
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    call_session = relationship("CallSession", back_populates="transcription", foreign_keys="[Transcription.call_session_id]", remote_side="[CallSession.id]")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "call_session_id": self.call_session_id,
            "raw_transcript": self.raw_transcript,
            "detected_language": self.detected_language,
            "language_probability": self.language_probability,
            "overall_confidence": self.overall_confidence,
            "stt_engine": self.stt_engine,
            "stt_status": self.stt_status,
            "processing_duration_ms": self.processing_duration_ms,
            "is_verbatim": self.is_verbatim,
            "ai_summary": self.ai_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AudioFile(Base):
    """Audio evidence file storage metadata."""

    __tablename__ = "audio_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    duration_seconds = Column(Float, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    storage_path = Column(String(500), nullable=False)  # Relative path in storage
    checksum = Column(String(64), nullable=True)  # SHA-256 checksum
    is_verified = Column(Boolean, default=False, nullable=False)  # Verified integrity
    call_session_id = Column(String(36), ForeignKey("call_sessions.id"), nullable=True, index=True)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    call_session = relationship("CallSession", back_populates="audio_file", foreign_keys="[AudioFile.call_session_id]", remote_side="[CallSession.id]")
    uploader = relationship("User", foreign_keys="[AudioFile.uploaded_by]")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "duration_seconds": self.duration_seconds,
            "storage_path": self.storage_path,
            "checksum": self.checksum,
            "is_verified": self.is_verified,
            "call_session_id": self.call_session_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Update Incident model to add call_session relationship
from backend.app.models.incident import Incident

Incident.call_session = relationship("CallSession", back_populates="incident", uselist=False)
