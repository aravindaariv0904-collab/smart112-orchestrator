from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.security import ACTOR_MAX_LENGTH, sanitize_text


class IncidentCreate(BaseModel):
    description: str = Field(
        ...,
        min_length=3,
        max_length=5000,
        description="Incident report narrative or caller speech transcript.",
    )
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    address: Optional[str] = Field(default=None, max_length=255)
    caller_phone: Optional[str] = Field(default=None, max_length=50)

    @field_validator("description", "address", "caller_phone", mode="before")
    @classmethod
    def sanitize_inputs(cls, value):
        return sanitize_text(value, max_length=5000)


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
    assigned_unit_id: Optional[str] = None
    assigned_unit_callsign: Optional[str] = None
    assigned_unit_type: Optional[str] = None


class IncidentStatusUpdate(BaseModel):
    status: str = Field(..., max_length=50)
    dispatcher_id: Optional[str] = Field(default="SYSTEM", max_length=ACTOR_MAX_LENGTH)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("dispatcher_id", "notes", mode="before")
    @classmethod
    def sanitize_update_inputs(cls, value):
        return sanitize_text(value, max_length=1000)
