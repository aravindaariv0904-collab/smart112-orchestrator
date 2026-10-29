from typing import List, Dict, Any
from pydantic import BaseModel, Field

class AssessmentData(BaseModel):
    incident_type: str = "GENERAL_EMERGENCY"
    casualty_count: int = Field(default=0, ge=0)
    hazards: List[str] = Field(default_factory=list)
    location_markers: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    uncertainty_detected: bool = False
    uncertainty_flags: List[str] = Field(default_factory=list)
    severity: str = "LEVEL_3_MODERATE"
    requires_human_review: bool = False
    confidence_score: float = Field(default=0.85, ge=0.0, le=1.0)
    structured_facts: Dict[str, Any] = Field(default_factory=dict)
