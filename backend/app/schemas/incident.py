import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator

def sanitize_string(v: Optional[str], max_length: int = 5000) -> Optional[str]:
    if v is None:
        return None
    # Strip dangerous HTML/script tags
    cleaned = re.sub(r"<[^>]*>", "", v)
    # Remove null bytes and non-printable control characters (except newline/tab)
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", cleaned)
    return cleaned.strip()[:max_length]

class IncidentCreate(BaseModel):
    description: str = Field(..., min_length=3, max_length=5000, description="Incident report narrative or caller speech transcript.")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    address: Optional[str] = Field(default=None, max_length=255)
    caller_phone: Optional[str] = Field(default=None, max_length=50)

    @field_validator("description", "address", "caller_phone", mode="before")
    @classmethod
    def sanitize_inputs(cls, value):
        if isinstance(value, str):
            return sanitize_string(value)
        return value

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
    status: str = Field(..., max_length=50)
    dispatcher_id: Optional[str] = Field(default="SYSTEM", max_length=50)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("dispatcher_id", "notes", mode="before")
    @classmethod
    def sanitize_update_inputs(cls, value):
        if isinstance(value, str):
            return sanitize_string(value, max_length=1000)
        return value
