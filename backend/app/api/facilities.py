"""
Hospital and Facility Management API

Provides endpoints for:
- Managing healthcare facilities (hospitals, clinics, blood banks)
- Tracking facility departments and specialties
- Managing bed capacity and availability
- Patient handover records
- Facility search and location-based queries
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from backend.app.core.database import get_db, Session
from backend.app.models.facilities import (
    Facility,
    HospitalDepartment,
    PatientHandover,
)
from backend.app.models.unit import EmergencyUnit
from backend.app.services.spatial import haversine_distance

logger = logging.getLogger("smart112.api.facilities")
router = APIRouter(prefix="/api/v1/facilities", tags=["facilities"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class FacilityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    facility_type: str = Field(..., pattern=r"^(HOSPITAL|CLINIC|BLOOD_BANK|FIRESTATION|EMERGENCY_STATION|POLICE_STATION|OTHER)$")
    address: str = Field(..., max_length=500)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=200)
    timezone: str = Field(default="Asia/Kolkata")
    # Hospital-specific
    has_emergency: bool = False
    has_icu: bool = False
    has_operating_theatre: bool = False
    bed_count: Optional[int] = Field(None, ge=0, le=10000)
    available_beds: Optional[int] = Field(None, ge=0)
    # Blood bank specific
    blood_types_available: Optional[List[str]] = Field(None, max_length=10)
    # Other
    description: Optional[str] = Field(None, max_length=1000)
    contact_person: Optional[str] = Field(None, max_length=200)
    operating_hours: Optional[str] = Field(None, max_length=200)
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None

class FacilityUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=500)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=200)
    has_emergency: Optional[bool] = None
    has_icu: Optional[bool] = None
    has_operating_theatre: Optional[bool] = None
    bed_count: Optional[int] = Field(None, ge=0, le=10000)
    available_beds: Optional[int] = Field(None, ge=0)
    blood_types_available: Optional[List[str]] = None
    description: Optional[str] = Field(None, max_length=1000)
    contact_person: Optional[str] = Field(None, max_length=200)
    operating_hours: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None

class FacilityResponse(BaseModel):
    id: str
    name: str
    facility_type: str
    address: str
    latitude: float
    longitude: float
    phone: Optional[str]
    email: Optional[str]
    timezone: str
    has_emergency: bool
    has_icu: bool
    has_operating_theatre: bool
    bed_count: Optional[int]
    available_beds: Optional[int]
    blood_types_available: Optional[List[str]]
    description: Optional[str]
    contact_person: Optional[str]
    operating_hours: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Computed
    distance_km: Optional[float] = None
    facilities_within_5km: int = 0

    class Config:
        from_attributes = True

class HandoverCompleteRequest(BaseModel):
    actual_arrival_time: Optional[datetime] = None
    handover_notes: Optional[str] = Field(None, max_length=2000)
    receiving_doctor: Optional[str] = Field(None, max_length=200)

class DepartmentCreate(BaseModel):
    facility_id: str = Field(..., max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    department_type: str = Field(..., pattern=r"^(EMERGENCY|ICU|GENERAL|PAEDIATRIC|ORTHOPAEDIC|CARDIOLOGY|NEUROLOGY|ONCOLOGY|BLOOD_BANK|SURGICAL|OTHER)$")
    specialist_count: Optional[int] = Field(default=0, ge=0)
    bed_count: Optional[int] = Field(default=0, ge=0)
    available_beds: Optional[int] = Field(default=0)
    has_24x7_service: bool = False
    phone: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=500)

class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    specialist_count: Optional[int] = Field(None, ge=0)
    bed_count: Optional[int] = Field(None, ge=0)
    available_beds: Optional[int] = Field(None, ge=0)
    has_24x7_service: Optional[bool] = None
    phone: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=500)

class DepartmentResponse(BaseModel):
    id: str
    facility_id: str
    name: str
    department_type: str
    specialist_count: int
    bed_count: int
    available_beds: int
    has_24x7_service: bool
    phone: Optional[str]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class HandoverCompleteRequest(BaseModel):
    actual_arrival_time: Optional[datetime] = None
    handover_notes: Optional[str] = Field(None, max_length=2000)
    receiving_doctor: Optional[str] = Field(None, max_length=200)

class PatientHandoverCreate(BaseModel):
    from_unit_id: str = Field(..., max_length=100)
    to_facility_id: str = Field(..., max_length=100)
    patient_name: str = Field(..., min_length=1, max_length=200)
    patient_age: Optional[int] = Field(None, ge=0, le=150)
    patient_gender: Optional[str] = Field(None, pattern=r"^(MALE|FEMALE|OTHER)$")
    incident_id: Optional[str] = Field(None, max_length=100)
    handover_reason: str = Field(..., max_length=500)
    transport_mode: str = Field(..., pattern=r"^(AMBULANCE|HELICOPTER|PRIVATE_VEHICLE|WALKING|OTHER)$")
    estimated_arrival_time: Optional[datetime] = None
    actual_arrival_time: Optional[datetime] = None
    handover_notes: Optional[str] = Field(None, max_length=2000)
    receiving_doctor: Optional[str] = Field(None, max_length=200)
    transferring_responder_id: Optional[str] = Field(None, max_length=100)

class PatientHandoverResponse(BaseModel):
    id: str
    from_unit_id: str
    to_facility_id: str
    patient_name: str
    patient_age: Optional[int]
    patient_gender: Optional[str]
    incident_id: Optional[str]
    handover_reason: str
    transport_mode: str
    status: str
    estimated_arrival_time: Optional[datetime]
    actual_arrival_time: Optional[datetime]
    handover_notes: Optional[str]
    receiving_doctor: Optional[str]
    transferring_responder_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    # Related
    facility_name: Optional[str] = None
    unit_callsign: Optional[str] = None

    class Config:
        from_attributes = True

class HandoverCompleteRequest(BaseModel):
    actual_arrival_time: Optional[datetime] = None
    handover_notes: Optional[str] = Field(None, max_length=2000)
    receiving_doctor: Optional[str] = Field(None, max_length=200)


# =============================================================================
# Facility Endpoints
# =============================================================================

@router.post("", response_model=FacilityResponse, status_code=status.HTTP_201_CREATED)
def create_facility(
    payload: FacilityCreate,
    db: Session = Depends(get_db),
):
    """Create a new healthcare facility or service location."""
    # Check for duplicate name at same location
    existing = db.query(Facility).filter(
        Facility.name.ilike(payload.name),
        Facility.latitude == payload.latitude,
        Facility.longitude == payload.longitude
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Facility with this name and location already exists"
        )
    
    facility = Facility(
        id=f"fac-{datetime.now(timezone.utc).timestamp()}",
        name=payload.name,
        facility_type=payload.facility_type,
        address=payload.address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        phone=payload.phone,
        email=payload.email,
        timezone=payload.timezone,
        has_emergency=payload.has_emergency,
        has_icu=payload.has_icu,
        has_operating_theatre=payload.has_operating_theatre,
        bed_count=payload.bed_count,
        available_beds=payload.available_beds,
        blood_types_available=payload.blood_types_available,
        description=payload.description,
        contact_person=payload.contact_person,
        operating_hours=payload.operating_hours,
        is_active=payload.is_active,
        facility_metadata=payload.metadata or {},
    )
    
    db.add(facility)
    db.commit()
    db.refresh(facility)
    
    logger.info("Created facility: %s (%s)", facility.name, facility.facility_type)
    return facility


@router.get("", response_model=List[FacilityResponse])
def list_facilities(
    facility_type: Optional[str] = Query(None, pattern=r"^(HOSPITAL|CLINIC|BLOOD_BANK|FIRESTATION|EMERGENCY_STATION|POLICE_STATION|OTHER)$"),
    has_emergency: Optional[bool] = Query(None),
    has_icu: Optional[bool] = Query(None),
    active_only: bool = Query(True),
    near_lat: Optional[float] = Query(None, ge=-90, le=90),
    near_lng: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: float = Query(10.0, ge=0.1, le=100.0),
    sort_by_distance: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    List facilities with filtering and location-based search.
    
    Supports:
    - Type filtering (hospital, clinic, blood bank, etc.)
    - Capability filtering (emergency, ICU, operating theatre)
    - Proximity search (find facilities near a location)
    - Distance sorting
    """
    query = db.query(Facility)
    
    if facility_type:
        query = query.filter(Facility.facility_type == facility_type)
    if has_emergency is not None:
        query = query.filter(Facility.has_emergency == has_emergency)
    if has_icu is not None:
        query = query.filter(Facility.has_icu == has_icu)
    if active_only:
        query = query.filter(Facility.is_active == True)
    
    facilities = query.all()
    
    # Apply proximity filter if location provided
    if near_lat and near_lng:
        filtered = []
        for fac in facilities:
            dist = haversine_distance(near_lat, near_lng, fac.latitude, fac.longitude)
            if dist <= radius_km:
                fac_dict = {
                    "id": fac.id,
                    "name": fac.name,
                    "facility_type": fac.facility_type,
                    "address": fac.address,
                    "latitude": fac.latitude,
                    "longitude": fac.longitude,
                    "phone": fac.phone,
                    "email": fac.email,
                    "timezone": fac.timezone,
                    "has_emergency": fac.has_emergency,
                    "has_icu": fac.has_icu,
                    "has_operating_theatre": fac.has_operating_theatre,
                    "bed_count": fac.bed_count,
                    "available_beds": fac.available_beds,
                    "blood_types_available": fac.blood_types_available,
                    "description": fac.description,
                    "contact_person": fac.contact_person,
                    "operating_hours": fac.operating_hours,
                    "is_active": fac.is_active,
                    "created_at": fac.created_at,
                    "updated_at": fac.updated_at,
                    "distance_km": round(dist, 2),
                }
                filtered.append(fac_dict)
        
        # Sort by distance if requested
        if sort_by_distance:
            filtered.sort(key=lambda x: x["distance_km"] or float('inf'))
        
        return filtered[:limit]
    
    return facilities[:limit]


@router.get("/{facility_id}", response_model=FacilityResponse)
def get_facility(
    facility_id: str,
    near_lat: Optional[float] = Query(None, ge=-90, le=90),
    near_lng: Optional[float] = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
):
    """Get a specific facility by ID."""
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Facility not found"
        )
    
    result = {
        "id": facility.id,
        "name": facility.name,
        "facility_type": facility.facility_type,
        "address": facility.address,
        "latitude": facility.latitude,
        "longitude": facility.longitude,
        "phone": facility.phone,
        "email": facility.email,
        "timezone": facility.timezone,
        "has_emergency": facility.has_emergency,
        "has_icu": facility.has_icu,
        "has_operating_theatre": facility.has_operating_theatre,
        "bed_count": facility.bed_count,
        "available_beds": facility.available_beds,
        "blood_types_available": facility.blood_types_available,
        "description": facility.description,
        "contact_person": facility.contact_person,
        "operating_hours": facility.operating_hours,
        "is_active": facility.is_active,
        "created_at": facility.created_at,
        "updated_at": facility.updated_at,
    }
    
    # Include distance if origin provided
    if near_lat and near_lng:
        result["distance_km"] = round(
            haversine_distance(near_lat, near_lng, facility.latitude, facility.longitude),
            2
        )
    
    # Count facilities within 5km
    all_facilities = db.query(Facility).filter(Facility.is_active == True).all()
    count_within_5km = 0
    for fac in all_facilities:
        if fac.id != facility.id:
            dist = haversine_distance(
                facility.latitude, facility.longitude,
                fac.latitude, fac.longitude
            )
            if dist <= 5.0:
                count_within_5km += 1
    
    result["facilities_within_5km"] = count_within_5km
    
    return result


@router.put("/{facility_id}", response_model=FacilityResponse)
def update_facility(
    facility_id: str,
    payload: FacilityUpdate,
    db: Session = Depends(get_db),
):
    """Update a facility's information."""
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Facility not found"
        )
    
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(facility, field, value)
    
    facility.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(facility)
    
    logger.info("Updated facility: %s", facility.name)
    return facility


@router.delete("/{facility_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_facility(
    facility_id: str,
    db: Session = Depends(get_db),
):
    """Soft delete a facility (sets is_active=False)."""
    facility = db.query(Facility).filter(Facility.id == facility_id).first()
    if not facility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Facility not found"
        )
    
    facility.is_active = False
    facility.updated_at = datetime.now(timezone.utc)
    db.commit()
    
    logger.info("Deleted facility: %s", facility.name)
    return None


# =============================================================================
# Department Management
# =============================================================================

@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
):
    """Create a department within a facility."""
    # Verify facility exists
    facility = db.query(Facility).filter(Facility.id == payload.facility_id).first()
    if not facility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Facility not found"
        )
    
    department = HospitalDepartment(
        id=f"dept-{datetime.now(timezone.utc).timestamp()}",
        facility_id=payload.facility_id,
        name=payload.name,
        department_type=payload.department_type,
        specialist_count=payload.specialist_count or 0,
        bed_count=payload.bed_count or 0,
        available_beds=payload.available_beds or 0,
        has_24x7_service=payload.has_24x7_service,
        phone=payload.phone,
        description=payload.description,
    )
    
    db.add(department)
    db.commit()
    db.refresh(department)
    
    logger.info("Created department: %s at %s", department.name, facility.name)
    return department


@router.get("/departments", response_model=List[DepartmentResponse])
def list_departments(
    facility_id: Optional[str] = Query(None, max_length=100),
    department_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List departments, optionally filtered by facility or type."""
    query = db.query(HospitalDepartment)
    
    if facility_id:
        query = query.filter(HospitalDepartment.facility_id == facility_id)
    if department_type:
        query = query.filter(HospitalDepartment.department_type == department_type)
    
    departments = query.all()
    return departments


@router.get("/departments/{department_id}", response_model=DepartmentResponse)
def get_department(
    department_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific department by ID."""
    department = db.query(HospitalDepartment).filter(
        HospitalDepartment.id == department_id
    ).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    return department


@router.put("/departments/{department_id}", response_model=DepartmentResponse)
def update_department(
    department_id: str,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
):
    """Update a department's information."""
    department = db.query(HospitalDepartment).filter(
        HospitalDepartment.id == department_id
    ).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    if payload.name is not None:
        department.name = payload.name
    if payload.specialist_count is not None:
        department.specialist_count = payload.specialist_count
    if payload.bed_count is not None:
        department.bed_count = payload.bed_count
    if payload.available_beds is not None:
        department.available_beds = payload.available_beds
    if payload.has_24x7_service is not None:
        department.has_24x7_service = payload.has_24x7_service
    if payload.phone is not None:
        department.phone = payload.phone
    if payload.description is not None:
        department.description = payload.description
    
    department.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(department)
    
    return department


# =============================================================================
# Patient Handover Management
# =============================================================================

@router.post("/handovers", response_model=PatientHandoverResponse, status_code=status.HTTP_201_CREATED)
def create_patient_handover(
    payload: PatientHandoverCreate,
    db: Session = Depends(get_db),
):
    """Create a patient handover record."""
    # Verify unit exists
    unit = db.query(EmergencyUnit).filter(EmergencyUnit.id == payload.from_unit_id).first()
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transport unit not found"
        )
    
    # Verify facility exists
    facility = db.query(Facility).filter(Facility.id == payload.to_facility_id).first()
    if not facility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiving facility not found"
        )
    
    handover = PatientHandover(
        id=f"handover-{datetime.now(timezone.utc).timestamp()}",
        from_unit_id=payload.from_unit_id,
        to_facility_id=payload.to_facility_id,
        patient_name=payload.patient_name,
        patient_age=payload.patient_age,
        patient_gender=payload.patient_gender,
        incident_id=payload.incident_id,
        handover_reason=payload.handover_reason,
        transport_mode=payload.transport_mode,
        status="IN_TRANSIT" if not payload.actual_arrival_time else "COMPLETED",
        estimated_arrival_time=payload.estimated_arrival_time,
        actual_arrival_time=payload.actual_arrival_time,
        handover_notes=payload.handover_notes,
        receiving_doctor=payload.receiving_doctor,
        transferring_responder_id=payload.transferring_responder_id,
    )
    
    db.add(handover)
    db.commit()
    db.refresh(handover)
    
    # Add facility name and unit callsign for response
    return {
        "id": handover.id,
        "from_unit_id": handover.from_unit_id,
        "to_facility_id": handover.to_facility_id,
        "patient_name": handover.patient_name,
        "patient_age": handover.patient_age,
        "patient_gender": handover.patient_gender,
        "incident_id": handover.incident_id,
        "handover_reason": handover.handover_reason,
        "transport_mode": handover.transport_mode,
        "status": handover.status,
        "estimated_arrival_time": handover.estimated_arrival_time,
        "actual_arrival_time": handover.actual_arrival_time,
        "handover_notes": handover.handover_notes,
        "receiving_doctor": handover.receiving_doctor,
        "transferring_responder_id": handover.transferring_responder_id,
        "created_at": handover.created_at,
        "updated_at": handover.updated_at,
        "facility_name": facility.name,
        "unit_callsign": unit.callsign,
    }


@router.get("/handovers", response_model=List[PatientHandoverResponse])
def list_handovers(
    facility_id: Optional[str] = Query(None, max_length=100),
    unit_id: Optional[str] = Query(None, max_length=100),
    status: Optional[str] = Query(None, pattern=r"^(PENDING|IN_TRANSIT|COMPLETED|CANCELLED)$"),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List patient handovers with filtering."""
    query = db.query(PatientHandover)
    
    if facility_id:
        query = query.filter(PatientHandover.to_facility_id == facility_id)
    if unit_id:
        query = query.filter(PatientHandover.from_unit_id == unit_id)
    if status:
        query = query.filter(PatientHandover.status == status)
    if from_date:
        query = query.filter(PatientHandover.created_at >= from_date)
    if to_date:
        query = query.filter(PatientHandover.created_at <= to_date)
    
    handovers = query.order_by(PatientHandover.created_at.desc()).limit(limit).all()
    
    result = []
    for h in handovers:
        facility = db.query(Facility).filter(Facility.id == h.to_facility_id).first()
        unit = db.query(EmergencyUnit).filter(EmergencyUnit.id == h.from_unit_id).first()
        
        result.append({
            "id": h.id,
            "from_unit_id": h.from_unit_id,
            "to_facility_id": h.to_facility_id,
            "patient_name": h.patient_name,
            "patient_age": h.patient_age,
            "patient_gender": h.patient_gender,
            "incident_id": h.incident_id,
            "handover_reason": h.handover_reason,
            "transport_mode": h.transport_mode,
            "status": h.status,
            "estimated_arrival_time": h.estimated_arrival_time,
            "actual_arrival_time": h.actual_arrival_time,
            "handover_notes": h.handover_notes,
            "receiving_doctor": h.receiving_doctor,
            "transferring_responder_id": h.transferring_responder_id,
            "created_at": h.created_at,
            "updated_at": h.updated_at,
            "facility_name": facility.name if facility else None,
            "unit_callsign": unit.callsign if unit else None,
        })
    
    return result


@router.get("/handovers/{handover_id}", response_model=PatientHandoverResponse)
def get_handover(
    handover_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific patient handover by ID."""
    handover = db.query(PatientHandover).filter(
        PatientHandover.id == handover_id
    ).first()
    if not handover:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handover not found"
        )
    
    facility = db.query(Facility).filter(Facility.id == handover.to_facility_id).first()
    unit = db.query(EmergencyUnit).filter(EmergencyUnit.id == handover.from_unit_id).first()
    
    return {
        "id": handover.id,
        "from_unit_id": handover.from_unit_id,
        "to_facility_id": handover.to_facility_id,
        "patient_name": handover.patient_name,
        "patient_age": handover.patient_age,
        "patient_gender": handover.patient_gender,
        "incident_id": handover.incident_id,
        "handover_reason": handover.handover_reason,
        "transport_mode": handover.transport_mode,
        "status": handover.status,
        "estimated_arrival_time": handover.estimated_arrival_time,
        "actual_arrival_time": handover.actual_arrival_time,
        "handover_notes": handover.handover_notes,
        "receiving_doctor": handover.receiving_doctor,
        "transferring_responder_id": handover.transferring_responder_id,
        "created_at": handover.created_at,
        "updated_at": handover.updated_at,
        "facility_name": facility.name if facility else None,
        "unit_callsign": unit.callsign if unit else None,
    }


@router.put("/handovers/{handover_id}/complete", response_model=PatientHandoverResponse)
def complete_handover(
    handover_id: str,
    payload: Optional[HandoverCompleteRequest] = None,
    db: Session = Depends(get_db),
):
    """Mark a patient handover as completed."""
    handover = db.query(PatientHandover).filter(
        PatientHandover.id == handover_id
    ).first()
    if not handover:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handover not found"
        )
    
    actual_arrival_time = payload.actual_arrival_time if payload else None
    handover_notes = payload.handover_notes if payload else None
    receiving_doctor = payload.receiving_doctor if payload else None
    
    handover.status = "COMPLETED"
    handover.actual_arrival_time = actual_arrival_time or datetime.now(timezone.utc)
    if handover_notes:
        handover.handover_notes = handover_notes
    if receiving_doctor:
        handover.receiving_doctor = receiving_doctor
    
    handover.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(handover)
    
    facility = db.query(Facility).filter(Facility.id == handover.to_facility_id).first()
    unit = db.query(EmergencyUnit).filter(EmergencyUnit.id == handover.from_unit_id).first()
    
    logger.info("Completed handover: %s to %s", handover.patient_name, facility.name if facility else "Unknown")
    
    return {
        "id": handover.id,
        "from_unit_id": handover.from_unit_id,
        "to_facility_id": handover.to_facility_id,
        "patient_name": handover.patient_name,
        "patient_age": handover.patient_age,
        "patient_gender": handover.patient_gender,
        "incident_id": handover.incident_id,
        "handover_reason": handover.handover_reason,
        "transport_mode": handover.transport_mode,
        "status": handover.status,
        "estimated_arrival_time": handover.estimated_arrival_time,
        "actual_arrival_time": handover.actual_arrival_time,
        "handover_notes": handover.handover_notes,
        "receiving_doctor": handover.receiving_doctor,
        "transferring_responder_id": handover.transferring_responder_id,
        "created_at": handover.created_at,
        "updated_at": handover.updated_at,
        "facility_name": facility.name if facility else None,
        "unit_callsign": unit.callsign if unit else None,
    }
