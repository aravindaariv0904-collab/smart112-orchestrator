from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

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
    unit_id: str = Field(..., description="Selected emergency unit ID.")
    dispatcher_id: str = Field(..., min_length=1, description="Authenticated human dispatcher ID.")
    notes: Optional[str] = None

class DispatchResponse(BaseModel):
    dispatch_id: str
    incident_id: str
    unit_id: str
    dispatcher_id: str
    status: str
    timestamp: str
    notes: Optional[str] = None

class UnitStatusUpdate(BaseModel):
    status: str = Field(..., description="Target status: AVAILABLE, DISPATCHED, ON_SCENE")
    dispatcher_id: Optional[str] = "SYSTEM"
    notes: Optional[str] = None
