import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

def sanitize_string(v: Optional[str], max_length: int = 2000) -> Optional[str]:
    if v is None:
        return None
    cleaned = re.sub(r"<[^>]*>", "", v)
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", cleaned)
    return cleaned.strip()[:max_length]

class CandidateUnit(BaseModel):
    unit_id: str
    callsign: str
    type: str
    distance_km: float
    eta_minutes: float
    status: str
    station: Optional[str] = None
    latitude: float
    longitude: float

class RecommendationResponse(BaseModel):
    incident_id: str
    candidate_units: List[CandidateUnit]
    rationale: str

class DispatchApprovalRequest(BaseModel):
    unit_id: str = Field(..., min_length=1, max_length=100, description="Selected emergency unit ID.")
    dispatcher_id: str = Field(..., min_length=1, max_length=100, description="Authenticated human dispatcher ID.")
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("unit_id", "dispatcher_id", "notes", mode="before")
    @classmethod
    def sanitize_dispatch_inputs(cls, value):
        if isinstance(value, str):
            return sanitize_string(value, max_length=1000)
        return value

class DispatchConfirmationRequest(BaseModel):
    incident_id: str = Field(..., min_length=1, max_length=100, description="Incident ID to assign.")
    unit_id: str = Field(..., min_length=1, max_length=100, description="Selected emergency unit ID.")
    dispatcher_id: str = Field(default="DISPATCHER_AUTHORIZED", min_length=1, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("incident_id", "unit_id", "dispatcher_id", "notes", mode="before")
    @classmethod
    def sanitize_confirm_inputs(cls, value):
        if isinstance(value, str):
            return sanitize_string(value, max_length=1000)
        return value

class DispatchResponse(BaseModel):
    dispatch_id: str
    incident_id: str
    unit_id: str
    dispatcher_id: str
    status: str
    timestamp: str
    notes: Optional[str] = None

class UnitStatusUpdate(BaseModel):
    status: str = Field(..., max_length=50, description="Target status: AVAILABLE, DISPATCHED, ON_SCENE, RESOLVED")
    dispatcher_id: Optional[str] = Field(default="SYSTEM", max_length=100)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("status", "dispatcher_id", "notes", mode="before")
    @classmethod
    def sanitize_status_inputs(cls, value):
        if isinstance(value, str):
            return sanitize_string(value, max_length=1000)
        return value
