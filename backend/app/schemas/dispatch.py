from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.security import ACTOR_MAX_LENGTH, sanitize_text


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
    dispatcher_id: str = Field(
        ...,
        min_length=1,
        max_length=ACTOR_MAX_LENGTH,
        description="Authenticated human dispatcher ID.",
    )
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("unit_id", "dispatcher_id", "notes", mode="before")
    @classmethod
    def sanitize_dispatch_inputs(cls, value):
        return sanitize_text(value, max_length=1000)


class DispatchConfirmationRequest(BaseModel):
    incident_id: str = Field(..., min_length=1, max_length=100, description="Incident ID to assign.")
    unit_id: str = Field(..., min_length=1, max_length=100, description="Selected emergency unit ID.")
    dispatcher_id: str = Field(
        default="DISPATCHER_AUTHORIZED", min_length=1, max_length=ACTOR_MAX_LENGTH
    )
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("incident_id", "unit_id", "dispatcher_id", "notes", mode="before")
    @classmethod
    def sanitize_confirm_inputs(cls, value):
        return sanitize_text(value, max_length=1000)


class DispatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dispatch_id: str
    incident_id: str
    unit_id: str
    dispatcher_id: str
    status: str
    timestamp: Union[str, datetime]
    notes: Optional[str] = None


class UnitStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        max_length=50,
        description="Target status: AVAILABLE, DISPATCHED, ON_SCENE, RESOLVED",
    )
    dispatcher_id: Optional[str] = Field(default="SYSTEM", max_length=ACTOR_MAX_LENGTH)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("status", "dispatcher_id", "notes", mode="before")
    @classmethod
    def sanitize_status_inputs(cls, value):
        return sanitize_text(value, max_length=1000)
