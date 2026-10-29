import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from backend.app.core.database import Base

class DispatchAssignment(Base):
    __tablename__ = "dispatch_assignments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False, index=True)
    unit_id = Column(String(36), ForeignKey("emergency_units.id"), nullable=False, index=True)
    dispatcher_id = Column(String(50), nullable=False)
    status = Column(String(50), default="DISPATCHED", nullable=False)  # DISPATCHED, ON_SCENE, RESOLVED, CANCELLED
    notes = Column(Text, nullable=True)
    
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    on_scene_at = Column(DateTime(timezone=True), nullable=True)
    cleared_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "dispatch_id": self.id,
            "incident_id": self.incident_id,
            "unit_id": self.unit_id,
            "dispatcher_id": self.dispatcher_id,
            "status": self.status,
            "notes": self.notes,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "on_scene_at": self.on_scene_at.isoformat() if self.on_scene_at else None,
            "cleared_at": self.cleared_at.isoformat() if self.cleared_at else None,
        }
