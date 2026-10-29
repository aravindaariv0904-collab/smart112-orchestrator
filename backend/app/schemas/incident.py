from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class IncidentCreate(BaseModel):
    description: str = Field(..., min_length=3, description="Incident report narrative or caller speech transcript.")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    address: Optional[str] = None
    caller_phone: Optional[str] = None

class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_number: str
    description: str
    category: str
    status: str
    severity: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    requires_human_review: bool
    assessment_data: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class IncidentStatusUpdate(BaseModel):
    status: str
    dispatcher_id: Optional[str] = "SYSTEM"
    notes: Optional[str] = None
