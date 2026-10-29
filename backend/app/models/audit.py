import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime
from backend.app.core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id = Column(String(36), index=True, nullable=False)
    actor = Column(String(50), nullable=False)  # DISPATCHER_ID, SYSTEM_AI, UNIT_CALLSIGN, etc.
    action = Column(String(100), nullable=False) # INCIDENT_CREATED, ASSESSMENT_APPLIED, DISPATCH_APPROVED, etc.
    details = Column(Text, nullable=False)      # JSON or formatted message
    
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "actor": self.actor,
            "action": self.action,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
