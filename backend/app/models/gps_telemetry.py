"""GPS telemetry and location tracking models."""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class Vehicle(Base):
    """Emergency vehicle with capability and equipment tracking."""

    __tablename__ = "vehicles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    vehicle_id = Column(String(50), unique=True, nullable=False, index=True)
    unit_id = Column(String(36), ForeignKey("emergency_units.id"), unique=True, nullable=False, index=True)
    make = Column(String(50), nullable=True)
    model = Column(String(50), nullable=True)
    year = Column(Integer, nullable=True)
    color = Column(String(50), nullable=True)
    license_plate = Column(String(20), nullable=True)
    vin = Column(String(17), nullable=True)
    capabilities = Column(String(500), default="", nullable=False)
    medical_equipment = Column(String(500), default="", nullable=False)
    radio_channel = Column(String(50), nullable=True)
    ais_operational = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    unit = relationship("EmergencyUnit", back_populates="vehicle")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "unit_id": self.unit_id,
            "make": self.make,
            "model": self.model,
            "year": self.year,
            "color": self.color,
            "license_plate": self.license_plate,
            "capabilities": self.get_capabilities(),
            "medical_equipment": self.get_medical_equipment(),
            "radio_channel": self.radio_channel,
            "ais_operational": self.ais_operational,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def get_capabilities(self) -> list[str]:
        return [c.strip() for c in self.capabilities.split(",") if c.strip()]

    def get_medical_equipment(self) -> list[str]:
        return [e.strip() for e in self.medical_equipment.split(",") if e.strip()]


class GPSDevice(Base):
    """Registered GPS tracking device."""

    __tablename__ = "gps_devices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    device_id = Column(String(50), unique=True, nullable=False, index=True)
    vehicle_id = Column(String(36), ForeignKey("vehicles.id"), nullable=True, index=True)
    unit_id = Column(String(36), ForeignKey("emergency_units.id"), nullable=True, index=True)
    responder_id = Column(String(36), ForeignKey("responders.id"), nullable=True, index=True)
    device_type = Column(String(50), default="mobile", nullable=False)
    manufacturer = Column(String(50), nullable=True)
    model = Column(String(50), nullable=True)
    firmware_version = Column(String(50), nullable=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    battery_level = Column(Float, nullable=True)
    signal_strength = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    vehicle = relationship("Vehicle", backref="gps_devices")
    unit = relationship("EmergencyUnit", overlaps="gps_devices")
    responder = relationship("Responder", overlaps="gps_devices")
    telemetry_readings = relationship("GPSReading", foreign_keys="[GPSReading.device_ref_id]", back_populates="device", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "vehicle_id": self.vehicle_id,
            "responder_id": self.responder_id,
            "device_type": self.device_type,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "firmware_version": self.firmware_version,
            "last_heartbeat_at": self.last_heartbeat_at.isoformat() if self.last_heartbeat_at else None,
            "battery_level": self.battery_level,
            "signal_strength": self.signal_strength,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class GPSReading(Base):
    """Individual GPS coordinate reading with metadata."""

    __tablename__ = "gps_readings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    device_ref_id = Column(String(36), ForeignKey("gps_devices.id"), nullable=True, index=True)
    device_id = Column(String(50), nullable=True, index=True)
    unit_id = Column(String(36), ForeignKey("emergency_units.id"), nullable=True, index=True)
    responder_id = Column(String(36), ForeignKey("responders.id"), nullable=True, index=True)
    reading_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float, nullable=True)
    speed_kmh = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    heading_degrees = Column(Float, nullable=True)
    accuracy_meters = Column(Float, nullable=True)
    battery_level = Column(Float, nullable=True)
    signal_strength = Column(Integer, nullable=True)
    hdop = Column(Float, nullable=True)
    vdop = Column(Float, nullable=True)
    satellites_used = Column(Integer, nullable=True)
    gps_signal_status = Column(String(20), default="good", nullable=False)
    is_stale = Column(Boolean, default=False, nullable=False)
    is_valid = Column(Boolean, default=True, nullable=False)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=True, index=True)
    assignment_id = Column(String(36), ForeignKey("dispatch_assignments.id", use_alter=True, name="fk_gps_readings_assignment"), nullable=True, index=True)
    telemetry_metadata = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    device = relationship("GPSDevice", foreign_keys=[device_ref_id], back_populates="telemetry_readings")
    incident = relationship("Incident", foreign_keys=[incident_id])
    assignment = relationship("DispatchAssignment", foreign_keys=[assignment_id])

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "unit_id": self.unit_id,
            "responder_id": self.responder_id,
            "reading_timestamp": (self.reading_timestamp or self.recorded_at).isoformat() if (self.reading_timestamp or self.recorded_at) else None,
            "recorded_at": (self.recorded_at or self.reading_timestamp).isoformat() if (self.recorded_at or self.reading_timestamp) else None,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "speed_kmh": self.speed_kmh,
            "heading": self.heading or self.heading_degrees,
            "heading_degrees": self.heading_degrees or self.heading,
            "accuracy_meters": self.accuracy_meters,
            "battery_level": self.battery_level,
            "signal_strength": self.signal_strength,
            "hdop": self.hdop,
            "vdop": self.vdop,
            "satellites_used": self.satellites_used,
            "gps_signal_status": self.gps_signal_status,
            "is_stale": self.is_stale,
            "is_valid": self.is_valid,
            "incident_id": self.incident_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LocationHistory(Base):
    """Track historical location points for route reconstruction."""

    __tablename__ = "location_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    device_id = Column(String(50), nullable=True, index=True)
    unit_id = Column(String(36), nullable=True, index=True)
    responder_id = Column(String(36), nullable=True, index=True)
    entity_type = Column(String(50), default="vehicle", nullable=False)
    entity_id = Column(String(36), default="", nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float, nullable=True)
    speed_kmh = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id or self.unit_id or self.device_id or "",
            "latitude": self.latitude,
            "longitude": self.longitude,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Geofence(Base):
    """Geographic boundary for automatic detection."""

    __tablename__ = "geofences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(100), nullable=False)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=True, index=True)
    unit_id = Column(String(36), ForeignKey("emergency_units.id"), nullable=True, index=True)
    type = Column(String(50), default="CIRCLE", nullable=False)
    coordinates = Column(JSON, nullable=True, default=list)
    description = Column(String(500), nullable=True)
    alert_on_enter = Column(Boolean, default=True, nullable=False)
    alert_on_exit = Column(Boolean, default=True, nullable=False)
    entity_type = Column(String(50), default="custom", nullable=False)
    entity_id_ref = Column(String(36), nullable=True)
    center_latitude = Column(Float, default=0.0, nullable=False)
    center_longitude = Column(Float, default=0.0, nullable=False)
    radius_meters = Column(Float, default=1000.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    triggered_by_reading_id = Column(String(36), ForeignKey("gps_readings.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    incident = relationship("Incident", foreign_keys=[incident_id])
    triggering_reading = relationship("GPSReading", foreign_keys=[triggered_by_reading_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "incident_id": self.incident_id,
            "unit_id": self.unit_id,
            "type": self.type,
            "coordinates": self.coordinates or [{"lat": self.center_latitude, "lng": self.center_longitude, "radius_m": self.radius_meters}],
            "description": self.description,
            "entity_type": self.entity_type,
            "entity_id_ref": self.entity_id_ref,
            "center_latitude": self.center_latitude,
            "center_longitude": self.center_longitude,
            "radius_meters": self.radius_meters,
            "is_active": self.is_active,
            "alert_on_enter": self.alert_on_enter,
            "alert_on_exit": self.alert_on_exit,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def is_point_inside(self, latitude: float, longitude: float) -> bool:
        """Check if coordinates are inside geofence using Haversine."""
        from backend.app.services.matcher import haversine_distance_km
        lat = self.center_latitude
        lng = self.center_longitude
        rad = self.radius_meters
        if self.coordinates and isinstance(self.coordinates, list) and len(self.coordinates) > 0:
            first = self.coordinates[0]
            if isinstance(first, dict):
                lat = first.get("lat", lat)
                lng = first.get("lng", lng)
                rad = first.get("radius_m", rad)
        distance_km = haversine_distance_km(lat, lng, latitude, longitude)
        return distance_km * 1000 <= rad
