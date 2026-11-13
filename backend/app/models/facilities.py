"""Hospital and emergency facility management."""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class Facility(Base):
    """Emergency facility (hospital, clinic, blood bank, etc.)."""

    __tablename__ = "facilities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    facility_id = Column(String(50), unique=True, nullable=True, index=True, default=lambda: f"FAC-{str(uuid4())[:8].upper()}")
    name = Column(String(200), nullable=False)
    facility_type = Column(String(50), nullable=False)
    subtype = Column(String(50), nullable=True)
    address = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    phone = Column(String(50), nullable=True, default="")
    alternate_phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    timezone = Column(String(50), default="Asia/Kolkata", nullable=False)
    contact_person = Column(String(100), nullable=True)
    contact_role = Column(String(100), nullable=True)
    
    # Capabilities
    accepts_walk_ins = Column(Boolean, default=True, nullable=False)
    accepts_referrals = Column(Boolean, default=True, nullable=False)
    has_emergency = Column(Boolean, default=False, nullable=False)
    has_emergency_department = Column(Boolean, default=False, nullable=False)
    has_icu = Column(Boolean, default=False, nullable=False)
    has_trauma_center = Column(Boolean, default=False, nullable=False)
    has_operating_theatre = Column(Boolean, default=False, nullable=False)
    has_ambulance_bay = Column(Boolean, default=False, nullable=False)
    has_blood_bank = Column(Boolean, default=False, nullable=False)
    has_pharmacy = Column(Boolean, default=False, nullable=False)
    has_imaging = Column(Boolean, default=False, nullable=False)
    has_surgery = Column(Boolean, default=False, nullable=False)
    
    # Capacity tracking
    current_capacity = Column(Integer, nullable=True)
    max_capacity = Column(Integer, nullable=True)
    bed_count = Column(Integer, nullable=True)
    available_beds = Column(Integer, nullable=True)
    icu_beds_available = Column(Integer, nullable=True)
    general_beds_available = Column(Integer, nullable=True)
    operation_theaters_available = Column(Integer, nullable=True)
    ambulance_bays_available = Column(Integer, nullable=True)
    blood_types_available = Column(JSON, nullable=True, default=list)
    description = Column(Text, nullable=True)
    operating_hours = Column(String(200), nullable=True)
    
    # Operational status
    is_active = Column(Boolean, default=True, nullable=False)
    status = Column(String(50), default="operational", nullable=False)
    last_status_update = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    notes = Column(Text, nullable=True)
    accreditation = Column(String(200), nullable=True)
    insurance_accepted = Column(String(500), default="", nullable=False)
    payment_options = Column(String(500), default="", nullable=False)
    
    is_verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    data_source = Column(String(50), default="manual", nullable=False)
    facility_metadata = Column(JSON, nullable=True, default=dict)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    verified_by_user = relationship("User", foreign_keys=[verified_by])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "facility_id": self.facility_id,
            "name": self.name,
            "facility_type": self.facility_type,
            "subtype": self.subtype,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "phone": self.phone,
            "alternate_phone": self.alternate_phone,
            "has_emergency_department": self.has_emergency_department or self.has_emergency,
            "has_trauma_center": self.has_trauma_center or self.has_icu,
            "status": self.status,
            "current_capacity": self.current_capacity,
            "icu_beds_available": self.icu_beds_available,
            "ambulance_bays_available": self.ambulance_bays_available,
            "is_verified": self.is_verified,
            "data_source": self.data_source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def get_capabilities_list(self) -> list[str]:
        capabilities = []
        if self.has_emergency_department or self.has_emergency:
            capabilities.append("emergency_department")
        if self.has_trauma_center or self.has_icu:
            capabilities.append("trauma_center")
        if self.has_ambulance_bay:
            capabilities.append("ambulance_bay")
        if self.has_blood_bank:
            capabilities.append("blood_bank")
        if self.has_pharmacy:
            capabilities.append("pharmacy")
        if self.has_imaging:
            capabilities.append("imaging")
        if self.has_surgery or self.has_operating_theatre:
            capabilities.append("surgery")
        return capabilities


class HospitalDepartment(Base):
    """Specific department within a hospital facility."""

    __tablename__ = "hospital_departments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=False, index=True)
    name = Column(String(100), nullable=True)
    department_name = Column(String(100), nullable=True)
    department_type = Column(String(50), nullable=False)
    specialist_count = Column(Integer, default=0, nullable=False)
    bed_count = Column(Integer, default=0, nullable=False)
    available_beds = Column(Integer, default=0, nullable=False)
    has_24x7_service = Column(Boolean, default=False, nullable=False)
    phone = Column(String(50), nullable=True)
    extension = Column(String(20), nullable=True)
    is_open_24h = Column(Boolean, default=False, nullable=False)
    current_wait_time_minutes = Column(Integer, nullable=True)
    is_accepting_patients = Column(Boolean, default=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    facility = relationship("Facility", backref="departments")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "facility_id": self.facility_id,
            "name": self.name or self.department_name,
            "department_name": self.department_name or self.name,
            "department_type": self.department_type,
            "specialist_count": self.specialist_count,
            "bed_count": self.bed_count,
            "available_beds": self.available_beds,
            "has_24x7_service": self.has_24x7_service,
            "phone": self.phone,
            "extension": self.extension,
            "is_open_24h": self.is_open_24h,
            "current_wait_time_minutes": self.current_wait_time_minutes,
            "is_accepting_patients": self.is_accepting_patients,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PatientHandover(Base):
    """Patient handover record from responder to facility."""

    __tablename__ = "patient_handovers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    handover_id = Column(String(50), unique=True, nullable=True, index=True, default=lambda: f"HND-{str(uuid4())[:8].upper()}")
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=True, index=True)
    assignment_id = Column(String(36), ForeignKey("dispatch_assignments.id", use_alter=True, name="fk_handover_assignment"), nullable=True, index=True)
    from_unit_id = Column(String(36), ForeignKey("emergency_units.id"), nullable=True, index=True)
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=True, index=True)
    to_facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=True, index=True)
    department_id = Column(String(36), ForeignKey("hospital_departments.id"), nullable=True, index=True)
    responder_id = Column(String(36), ForeignKey("responders.id"), nullable=True, index=True)
    transferring_responder_id = Column(String(36), ForeignKey("responders.id"), nullable=True, index=True)
    patient_name = Column(String(200), nullable=True)
    patient_age = Column(Integer, nullable=True)
    patient_gender = Column(String(20), nullable=True)
    handover_reason = Column(String(500), nullable=True)
    transport_mode = Column(String(50), nullable=True)
    status = Column(String(50), default="IN_TRANSIT", nullable=False)
    estimated_arrival_time = Column(DateTime(timezone=True), nullable=True)
    actual_arrival_time = Column(DateTime(timezone=True), nullable=True)
    handover_notes = Column(Text, nullable=True)
    receiving_doctor = Column(String(200), nullable=True)
    patient_condition = Column(String(500), nullable=True)
    treatments_administered = Column(String(1000), nullable=True)
    vitals = Column(String(1000), nullable=True)
    handover_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    receiving_clinician = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    incident = relationship("Incident", foreign_keys=[incident_id])
    assignment = relationship("DispatchAssignment", foreign_keys=[assignment_id])
    facility = relationship("Facility", foreign_keys=[facility_id])
    to_facility = relationship("Facility", foreign_keys=[to_facility_id])
    department = relationship("HospitalDepartment", foreign_keys=[department_id])
    responder = relationship("Responder", foreign_keys=[responder_id])
    transferring_responder = relationship("Responder", foreign_keys=[transferring_responder_id])
    creator = relationship("User", foreign_keys=[created_by])

    def to_dict(self) -> dict:
        fac = self.to_facility or self.facility
        dept = self.department
        return {
            "id": self.id,
            "handover_id": self.handover_id,
            "incident_id": self.incident_id,
            "from_unit_id": self.from_unit_id,
            "to_facility_id": self.to_facility_id or self.facility_id,
            "facility_id": self.facility_id or self.to_facility_id,
            "facility_name": fac.name if fac else None,
            "department_id": self.department_id,
            "department_name": (dept.name or dept.department_name) if dept else None,
            "patient_name": self.patient_name,
            "patient_age": self.patient_age,
            "patient_gender": self.patient_gender,
            "patient_condition": self.patient_condition or self.handover_notes,
            "status": self.status,
            "estimated_arrival_time": self.estimated_arrival_time.isoformat() if self.estimated_arrival_time else None,
            "actual_arrival_time": self.actual_arrival_time.isoformat() if self.actual_arrival_time else None,
            "handover_time": self.handover_time.isoformat() if self.handover_time else None,
            "receiving_clinician": self.receiving_clinician or self.receiving_doctor,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Update DispatchAssignment model to add handover relationship
from backend.app.models.dispatch import DispatchAssignment

DispatchAssignment.handover = relationship("PatientHandover", back_populates="assignment", uselist=False)
