"""
GPS Telemetry API

Provides endpoints for:
- Ingesting GPS coordinates from vehicles and responders
- Querying recent readings and location history
- Real-time webhook for unit tracking updates
- Geofence management
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from pydantic import BaseModel, Field

from backend.app.core.database import get_db, Session
from backend.app.models.gps_telemetry import (
    GPSReading,
    GPSDevice,
    LocationHistory,
    Geofence,
    Vehicle,
)
from backend.app.models.unit import EmergencyUnit
from backend.app.models.user import Responder

logger = logging.getLogger("smart112.api.gps")
router = APIRouter(prefix="/api/v1/gps", tags=["gps"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class GPSReadingIngest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=100)
    unit_id: Optional[str] = Field(None, max_length=100)
    responder_id: Optional[str] = Field(None, max_length=100)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude: Optional[float] = Field(None, ge=-1000, le=10000)
    speed_kmh: Optional[float] = Field(None, ge=0, le=500)
    heading: Optional[float] = Field(None, ge=0, le=360)
    accuracy_meters: Optional[float] = Field(None, ge=0, le=1000)
    battery_level: Optional[float] = Field(None, ge=0, le=100)
    signal_strength: Optional[int] = Field(None, ge=-120, le=-30)
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class GPSReadingResponse(BaseModel):
    id: str
    device_id: str
    unit_id: Optional[str]
    responder_id: Optional[str]
    latitude: float
    longitude: float
    altitude: Optional[float]
    speed_kmh: Optional[float]
    heading: Optional[float]
    accuracy_meters: Optional[float]
    battery_level: Optional[float]
    signal_strength: Optional[int]
    recorded_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class LocationHistoryQuery(BaseModel):
    unit_id: Optional[str] = Field(None, max_length=100)
    responder_id: Optional[str] = Field(None, max_length=100)
    device_id: Optional[str] = Field(None, max_length=100)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=10000)

class LocationHistoryResponse(BaseModel):
    id: str
    entity_type: str = "vehicle"
    entity_id: str
    latitude: float
    longitude: float
    recorded_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UnitLocationResponse(BaseModel):
    unit_id: str
    unit_type: str
    callsign: str
    status: str
    latest_latitude: Optional[float]
    latest_longitude: Optional[float]
    latest_heading: Optional[float]
    latest_speed_kmh: Optional[float]
    latest_timestamp: Optional[datetime]
    last_update: Optional[datetime]
    distance_from_origin_km: Optional[float] = None

class GeofenceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    unit_id: Optional[str] = Field(None, max_length=100)
    type: str = Field(..., pattern=r"^(POLYGON|CIRCLE|BOUNDARY)$")
    coordinates: List[Dict[str, float]] = Field(..., min_length=1)
    # For CIRCLE: [{"lat": 16.3067, "lng": 80.4365, "radius_m": 500}]
    # For POLYGON: [{"lat": 16.3067, "lng": 80.4365}, ...]
    description: Optional[str] = Field(None, max_length=500)
    is_active: bool = True
    alert_on_enter: bool = True
    alert_on_exit: bool = True

class GeofenceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None
    alert_on_enter: Optional[bool] = None
    alert_on_exit: Optional[bool] = None
    description: Optional[str] = Field(None, max_length=500)

class GeofenceResponse(BaseModel):
    id: str
    name: str
    unit_id: Optional[str]
    type: str
    coordinates: List[Dict[str, float]]
    description: Optional[str]
    is_active: bool
    alert_on_enter: bool
    alert_on_exit: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class WebhookPayload(BaseModel):
    event_type: str = Field(..., pattern=r"^(UNIT_MOVED|UNIT_ARRIVED|UNIT_DEPARTED|GEOFENCE_ENTER|GEOFENCE_EXIT|LOW_BATTERY|OFFLINE)$")
    unit_id: str
    timestamp: datetime
    data: Dict[str, Any]


# =============================================================================
# GPS Reading Ingestion
# =============================================================================

@router.post("/readings", response_model=GPSReadingResponse, status_code=status.HTTP_201_CREATED)
def ingest_gps_reading(
    payload: GPSReadingIngest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Ingest a GPS coordinate reading from a device, vehicle, or responder.
    
    This endpoint accepts location updates from:
    - Vehicle GPS trackers
    - Responder mobile devices  
    - Emergency unit tracking systems
    
    Returns the created reading with its unique ID.
    """
    # Validate that at least one identifier is provided
    if not payload.device_id and not payload.unit_id and not payload.responder_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of device_id, unit_id, or responder_id must be provided"
        )
    
    # Use timestamp from payload or current time
    recorded_at = payload.timestamp or datetime.now(timezone.utc)
    
    # Create GPS reading
    reading = GPSReading(
        id=f"gps-{recorded_at.timestamp()}-{hash(payload.device_id or payload.unit_id or payload.responder_id) % 10000}",
        device_id=payload.device_id,
        unit_id=payload.unit_id,
        responder_id=payload.responder_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        altitude=payload.altitude,
        speed_kmh=payload.speed_kmh,
        heading=payload.heading,
        accuracy_meters=payload.accuracy_meters,
        battery_level=payload.battery_level,
        signal_strength=payload.signal_strength,
        recorded_at=recorded_at,
        telemetry_metadata=payload.metadata or {},
    )
    
    db.add(reading)
    
    # Update location history
    history = LocationHistory(
        id=f"hist-{reading.id}",
        device_id=payload.device_id,
        unit_id=payload.unit_id,
        responder_id=payload.responder_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        altitude=payload.altitude,
        speed_kmh=payload.speed_kmh,
        heading=payload.heading,
        recorded_at=recorded_at,
    )
    db.add(history)
    
    db.commit()
    db.refresh(reading)
    
    logger.info(
        "GPS reading ingested: device=%s, unit=%s, lat=%.6f, lng=%.6f, speed=%.1f km/h",
        payload.device_id or "N/A",
        payload.unit_id or "N/A",
        payload.latitude,
        payload.longitude,
        payload.speed_kmh or 0
    )
    
    # Schedule background tasks for real-time updates (webhook, notifications)
    # background_tasks.add_task(process_gps_event, reading)
    
    return reading


# =============================================================================
# Query Recent Readings
# =============================================================================

@router.get("/readings", response_model=List[GPSReadingResponse])
def get_recent_readings(
    device_id: Optional[str] = Query(None, max_length=100),
    unit_id: Optional[str] = Query(None, max_length=100),
    responder_id: Optional[str] = Query(None, max_length=100),
    minutes: int = Query(60, ge=1, le=1440),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    Get recent GPS readings for a device, unit, or responder.
    
    Returns readings from the last N minutes (default: 60 minutes).
    Results are ordered by timestamp descending (most recent first).
    """
    # Calculate time window
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    
    query = db.query(GPSReading).filter(GPSReading.recorded_at >= since)
    
    if device_id:
        query = query.filter(GPSReading.device_id == device_id)
    if unit_id:
        query = query.filter(GPSReading.unit_id == unit_id)
    if responder_id:
        query = query.filter(GPSReading.responder_id == responder_id)
    
    readings = query.order_by(GPSReading.recorded_at.desc()).limit(limit).all()
    return readings


@router.get("/readings/{reading_id}", response_model=GPSReadingResponse)
def get_reading_by_id(
    reading_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific GPS reading by ID."""
    reading = db.query(GPSReading).filter(GPSReading.id == reading_id).first()
    if not reading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GPS reading not found"
        )
    return reading


# =============================================================================
# Location History
# =============================================================================

@router.get("/history", response_model=List[LocationHistoryResponse])
def get_location_history(
    unit_id: Optional[str] = Query(None, max_length=100),
    responder_id: Optional[str] = Query(None, max_length=100),
    device_id: Optional[str] = Query(None, max_length=100),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    """
    Get location history for a unit, responder, or device.
    
    Returns historical location points ordered by time.
    Useful for tracking movements, route history, and incident reconstruction.
    """
    query = db.query(LocationHistory)
    
    if unit_id:
        query = query.filter(LocationHistory.entity_id == unit_id)
    elif responder_id:
        query = query.filter(LocationHistory.entity_id == responder_id)
    elif device_id:
        query = query.filter(LocationHistory.entity_id == device_id)
    
    if start_time:
        query = query.filter(LocationHistory.recorded_at >= start_time)
    if end_time:
        query = query.filter(LocationHistory.recorded_at <= end_time)
    
    history = query.order_by(LocationHistory.recorded_at.desc()).limit(limit).all()
    return history


# =============================================================================
# Unit Location Summaries
# =============================================================================

@router.get("/units/locations", response_model=List[UnitLocationResponse])
def get_unit_locations(
    unit_ids: Optional[str] = Query(None, description="Comma-separated list of unit IDs"),
    status_filter: Optional[str] = Query(None, pattern=r"^(AVAILABLE|DEPLOYED|EN_ROUTE|AT_SCENE|AWAY)$"),
    include_distance: bool = Query(False),
    origin_lat: Optional[float] = Query(None, ge=-90, le=90),
    origin_lng: Optional[float] = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
):
    """
    Get current location summaries for emergency units.
    
    Returns the latest known location for each unit with:
    - Unit details (type, callsign, status)
    - Latest GPS coordinates and heading
    - Optional distance from an origin point (for dispatch filtering)
    """
    # Parse unit IDs if provided
    target_unit_ids = None
    if unit_ids:
        target_unit_ids = [uid.strip() for uid in unit_ids.split(",") if uid.strip()]
    
    # Query units with optional filters
    query = db.query(EmergencyUnit)
    
    if target_unit_ids:
        query = query.filter(EmergencyUnit.id.in_(target_unit_ids))
    
    if status_filter:
        query = query.filter(EmergencyUnit.status == status_filter)
    
    units = query.all()
    
    result = []
    for unit in units:
        # Get latest GPS reading for this unit
        latest_reading = db.query(GPSReading).filter(
            GPSReading.unit_id == unit.id
        ).order_by(GPSReading.recorded_at.desc()).first()
        
        # Calculate distance if origin provided
        distance = None
        if include_distance and origin_lat and origin_lng and latest_reading:
            from backend.app.services.spatial import haversine_distance
            distance = haversine_distance(
                origin_lat, origin_lng,
                latest_reading.latitude, latest_reading.longitude
            )
        
        result.append({
            "unit_id": unit.id,
            "unit_type": unit.unit_type,
            "callsign": unit.callsign,
            "status": unit.status,
            "latest_latitude": latest_reading.latitude if latest_reading else None,
            "latest_longitude": latest_reading.longitude if latest_reading else None,
            "latest_heading": latest_reading.heading if latest_reading else None,
            "latest_speed_kmh": latest_reading.speed_kmh if latest_reading else None,
            "latest_timestamp": latest_reading.recorded_at if latest_reading else None,
            "last_update": latest_reading.created_at if latest_reading else None,
            "distance_from_origin_km": distance,
        })
    
    return result


@router.get("/units/{unit_id}/location", response_model=Optional[Dict[str, Any]])
def get_unit_current_location(
    unit_id: str,
    db: Session = Depends(get_db),
):
    """Get the current/latest location for a specific unit."""
    unit = db.query(EmergencyUnit).filter(EmergencyUnit.id == unit_id).first()
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unit not found"
        )
    
    latest_reading = db.query(GPSReading).filter(
        GPSReading.unit_id == unit_id
    ).order_by(GPSReading.recorded_at.desc()).first()
    
    if not latest_reading:
        return {
            "unit_id": unit_id,
            "callsign": unit.callsign,
            "status": unit.status,
            "location_available": False,
        }
    
    return {
        "unit_id": unit_id,
        "callsign": unit.callsign,
        "status": unit.status,
        "location_available": True,
        "latitude": latest_reading.latitude,
        "longitude": latest_reading.longitude,
        "altitude": latest_reading.altitude,
        "speed_kmh": latest_reading.speed_kmh,
        "heading": latest_reading.heading,
        "accuracy_meters": latest_reading.accuracy_meters,
        "battery_level": latest_reading.battery_level,
        "recorded_at": latest_reading.recorded_at,
        "received_at": latest_reading.created_at,
    }


# =============================================================================
# Geofence Management
# =============================================================================

@router.post("/geofences", response_model=GeofenceResponse, status_code=status.HTTP_201_CREATED)
def create_geofence(
    payload: GeofenceCreate,
    db: Session = Depends(get_db),
):
    """Create a new geofence for automatic boundary detection."""
    geofence = Geofence(
        id=f"geo-{datetime.now(timezone.utc).timestamp()}",
        name=payload.name,
        unit_id=payload.unit_id,
        type=payload.type,
        coordinates=payload.coordinates,
        description=payload.description,
        is_active=payload.is_active,
        alert_on_enter=payload.alert_on_enter,
        alert_on_exit=payload.alert_on_exit,
    )
    
    db.add(geofence)
    db.commit()
    db.refresh(geofence)
    
    logger.info("Created geofence: %s (type: %s)", geofence.name, geofence.type)
    return geofence


@router.get("/geofences", response_model=List[GeofenceResponse])
def list_geofences(
    unit_id: Optional[str] = Query(None, max_length=100),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    """List all geofences, optionally filtered by unit or active status."""
    query = db.query(Geofence)
    
    if unit_id:
        query = query.filter(Geofence.unit_id == unit_id)
    if active_only:
        query = query.filter(Geofence.is_active == True)
    
    geofences = query.order_by(Geofence.created_at.desc()).all()
    return geofences


@router.get("/geofences/{geofence_id}", response_model=GeofenceResponse)
def get_geofence(
    geofence_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific geofence by ID."""
    geofence = db.query(Geofence).filter(Geofence.id == geofence_id).first()
    if not geofence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geofence not found"
        )
    return geofence


@router.put("/geofences/{geofence_id}", response_model=GeofenceResponse)
def update_geofence(
    geofence_id: str,
    payload: GeofenceUpdate,
    db: Session = Depends(get_db),
):
    """Update a geofence's properties."""
    geofence = db.query(Geofence).filter(Geofence.id == geofence_id).first()
    if not geofence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geofence not found"
        )
    
    if payload.name is not None:
        geofence.name = payload.name
    if payload.is_active is not None:
        geofence.is_active = payload.is_active
    if payload.alert_on_enter is not None:
        geofence.alert_on_enter = payload.alert_on_enter
    if payload.alert_on_exit is not None:
        geofence.alert_on_exit = payload.alert_on_exit
    if payload.description is not None:
        geofence.description = payload.description
    
    geofence.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(geofence)
    
    logger.info("Updated geofence: %s", geofence.name)
    return geofence


@router.delete("/geofences/{geofence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_geofence(
    geofence_id: str,
    db: Session = Depends(get_db),
):
    """Delete a geofence."""
    geofence = db.query(Geofence).filter(Geofence.id == geofence_id).first()
    if not geofence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geofence not found"
        )
    
    db.delete(geofence)
    db.commit()
    
    logger.info("Deleted geofence: %s", geofence.name)
    return None


# =============================================================================
# Webhook Endpoint for Real-Time Updates
# =============================================================================

@router.post("/webhook")
async def receive_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
):
    """
    Receive real-time GPS events from external systems.
    
    This webhook endpoint accepts events from:
    - Vehicle GPS tracker systems
    - Third-party dispatch platforms
    - IoT device management systems
    
    Events are processed asynchronously and can trigger:
    - Unit status updates
    - Geofence alerts
    - Notification generation
    - Real-time dashboard updates
    """
    logger.info(
        "Webhook received: event=%s, unit=%s, timestamp=%s",
        payload.event_type,
        payload.unit_id,
        payload.timestamp
    )
    
    # Process webhook event asynchronously
    # background_tasks.add_task(handle_webhook_event, payload)
    
    return {"status": "received", "event_id": f"evt-{payload.timestamp.timestamp()}"}


# =============================================================================
# Device Management (for GPS device registration)
# =============================================================================

@router.get("/devices", response_model=List[Dict[str, Any]])
def list_gps_devices(
    unit_id: Optional[str] = Query(None, max_length=100),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    """List registered GPS devices."""
    query = db.query(GPSDevice)
    
    if unit_id:
        query = query.filter(GPSDevice.unit_id == unit_id)
    if active_only:
        query = query.filter(GPSDevice.is_active == True)
    
    devices = query.all()
    
    return [
        {
            "id": d.id,
            "device_id": d.device_id,
            "unit_id": d.unit_id,
            "vehicle_id": d.vehicle_id,
            "responder_id": d.responder_id,
            "device_type": d.device_type,
            "status": d.status,
            "last_seen": d.last_seen,
            "battery_level": d.battery_level,
            "is_active": d.is_active,
            "created_at": d.created_at,
        }
        for d in devices
    ]


@router.get("/devices/{device_id}", response_model=Optional[Dict[str, Any]])
def get_device(
    device_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific GPS device by ID."""
    device = db.query(GPSDevice).filter(GPSDevice.id == device_id).first()
    if not device:
        return None
    
    return {
        "id": device.id,
        "device_id": device.device_id,
        "unit_id": device.unit_id,
        "vehicle_id": device.vehicle_id,
        "responder_id": device.responder_id,
        "device_type": device.device_type,
        "status": device.status,
        "last_seen": device.last_seen,
        "battery_level": device.battery_level,
        "is_active": device.is_active,
        "created_at": device.created_at,
        "updated_at": device.updated_at,
    }
