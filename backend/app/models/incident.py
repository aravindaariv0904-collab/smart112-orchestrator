import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, Boolean, DateTime
from backend.app.core.database import Base

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_number = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), default="UNKNOWN", nullable=False)
    status = Column(String(50), default="REPORTED", nullable=False)
    severity = Column(String(50), default="LEVEL_3_MODERATE", nullable=False)
    
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(255), nullable=True)
    
    requires_human_review = Column(Boolean, default=False, nullable=False)
    assessment_data = Column(Text, nullable=True)  # JSON-serialized facts
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "incident_number": self.incident_number,
            "description": self.description,
            "category": self.category,
            "status": self.status,
            "severity": self.severity,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "address": self.address,
            "requires_human_review": self.requires_human_review,
            "assessment_data": self.assessment_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
