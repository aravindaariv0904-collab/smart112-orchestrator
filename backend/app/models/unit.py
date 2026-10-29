import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime
from backend.app.core.database import Base

class EmergencyUnit(Base):
    __tablename__ = "emergency_units"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    callsign = Column(String(50), unique=True, index=True, nullable=False)
    unit_type = Column(String(50), nullable=False)  # AMBULANCE, FIRE_TRUCK, POLICE_PATROL
    
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String(50), default="AVAILABLE", nullable=False)  # AVAILABLE, DISPATCHED, ON_SCENE
    station = Column(String(100), nullable=True)
    
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "callsign": self.callsign,
            "unit_type": self.unit_type,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "status": self.status,
            "station": self.station,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
