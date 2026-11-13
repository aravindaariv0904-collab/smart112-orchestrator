import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

class EmergencyUnit(Base):
    __tablename__ = "emergency_units"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    callsign = Column(String(50), unique=True, index=True, nullable=False)
    unit_type = Column(String(50), nullable=False)  # AMBULANCE, FIRE_TRUCK, POLICE_PATROL, RESCUE_SQUAD
    
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String(50), default="AVAILABLE", nullable=False)  # AVAILABLE, DISPATCHED, ON_SCENE
    station = Column(String(100), nullable=True)
    responder_id = Column(String(36), ForeignKey("responders.id"), nullable=True, index=True)
    
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships - using back_populates consistently
    vehicle = relationship("Vehicle", back_populates="unit", uselist=False)
    assigned_responder = relationship("Responder", back_populates="unit", foreign_keys="[Responder.unit_id]", uselist=False)
    dispatches = relationship("DispatchAssignment", back_populates="unit", order_by="desc(DispatchAssignment.timestamp)")
    gps_devices = relationship("GPSDevice", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "callsign": self.callsign,
            "unit_type": self.unit_type,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "status": self.status,
            "station": self.station,
            "responder_id": self.responder_id,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
