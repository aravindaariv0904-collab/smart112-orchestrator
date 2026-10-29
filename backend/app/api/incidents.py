import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.core.database import get_db
from backend.app.core.security import generate_uuid, sanitize_actor_id
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit
from backend.app.models.dispatch import DispatchAssignment
from backend.app.models.audit import AuditLog
from backend.app.schemas.incident import IncidentCreate, IncidentResponse, IncidentStatusUpdate
from backend.app.schemas.dispatch import RecommendationResponse, DispatchApprovalRequest, DispatchResponse
from backend.app.services.matcher import match_candidate_units
from backend.app.services.state_machine import validate_state_transition, InvalidStateTransitionError
from ai.extractor import extract_emergency_facts

logger = logging.getLogger("smart112.api.incidents")
router = APIRouter()

@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db)
):
    """
    Ingests and registers an emergency incident.
    Executes AI extraction with strict timeout, evaluates safety escalation rules,
    persists incident record, and appends an immutable entry to the AuditLog.
    """
    # 1. Run AI extraction and rule evaluation
    assessment = await extract_emergency_facts(payload.description)
    
    # Generate sequential incident number
    count = db.query(Incident).count() + 1
    incident_number = f"INC-2026-{count:04d}"
    incident_id = generate_uuid()
    
    # Determine category and severity from evaluation
    category = assessment.get("incident_type", "GENERAL_EMERGENCY")
    severity = assessment.get("severity", "LEVEL_3_MODERATE")
    requires_review = assessment.get("requires_human_review", False)

    # 2. Persist Incident
    incident = Incident(
        id=incident_id,
        incident_number=incident_number,
        description=payload.description,
        category=category,
        status="ASSESSED",
        severity=severity,
        latitude=payload.latitude,
        longitude=payload.longitude,
        address=payload.address or "Location verified via coordinates",
        requires_human_review=requires_review,
        assessment_data=json.dumps(assessment)
    )
    db.add(incident)

    # 3. Append to Immutable Audit Log
    audit = AuditLog(
        incident_id=incident_id,
        actor="SYSTEM_AI",
        action="INCIDENT_REPORTED_AND_ASSESSED",
        details=json.dumps({
            "incident_number": incident_number,
            "category": category,
            "severity": severity,
            "requires_human_review": requires_review,
            "casualty_count": assessment.get("casualty_count", 0),
            "hazards": assessment.get("hazards", []),
            "missing_information": assessment.get("missing_information", [])
        })
    )
    db.add(audit)
    db.commit()
    db.refresh(incident)

    logger.info(f"Incident {incident_number} created with severity {severity}. Audit logged.")
    return incident.to_dict()

@router.get("", response_model=List[IncidentResponse])
def list_incidents(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Returns active incidents sorted by severity priority and recency."""
    query = db.query(Incident)
    if status_filter:
        query = query.filter(Incident.status == status_filter.upper())
    
    incidents = query.order_by(
        desc(Incident.created_at)
    ).all()
    
    # Custom priority sorting: LEVEL_1_CRITICAL first
    severity_order = {
        "LEVEL_1_CRITICAL": 0,
        "LEVEL_2_HIGH": 1,
        "LEVEL_3_MODERATE": 2,
        "LEVEL_4_LOW": 3
    }
    incidents.sort(key=lambda x: severity_order.get(x.severity, 4))
    return [i.to_dict() for i in incidents]

@router.get("/{id}", response_model=IncidentResponse)
def get_incident(
    id: str,
    db: Session = Depends(get_db)
):
    """Returns details for a specific incident."""
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {id} not found."
        )
    return incident.to_dict()

@router.post("/{id}/recommend", response_model=RecommendationResponse)
def get_unit_recommendations(
    id: str,
    db: Session = Depends(get_db)
):
    """
    Executes spatial proximity query against PostGIS/spatial engine
    and returns top 3 recommended units with tactical rationale.
    Transitions incident status from ASSESSED -> RECOMMENDED.
    """
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    recommendation = match_candidate_units(db, incident, limit=3)
    
    # Transition to RECOMMENDED if currently in ASSESSED state
    if incident.status == "ASSESSED":
        try:
            validate_state_transition(incident.status, "RECOMMENDED")
            incident.status = "RECOMMENDED"
            audit = AuditLog(
                incident_id=incident.id,
                actor="SYSTEM_MATCHER",
                action="RECOMMENDATION_GENERATED",
                details=json.dumps({
                    "candidate_count": len(recommendation["candidate_units"]),
                    "top_unit": recommendation["candidate_units"][0]["callsign"] if recommendation["candidate_units"] else None
                })
            )
            db.add(audit)
            db.commit()
        except InvalidStateTransitionError as e:
            logger.warning(f"State transition skipped: {e}")

    return recommendation

@router.post("/{id}/approve-dispatch", response_model=DispatchResponse)
def approve_dispatch(
    id: str,
    payload: DispatchApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Human dispatcher authorization endpoint.
    Atomically locks and validates unit availability, updates unit and incident statuses,
    creates dispatch assignment, and records the action into the immutable audit ledger.
    """
    # 1. Fetch Incident and Unit (handling SQLite vs PostgreSQL row locking)
    is_sqlite = db.bind.dialect.name == "sqlite" if db.bind else False
    inc_query = db.query(Incident).filter(Incident.id == id)
    unit_query = db.query(EmergencyUnit).filter(EmergencyUnit.id == payload.unit_id)
    if not is_sqlite:
        inc_query = inc_query.with_for_update()
        unit_query = unit_query.with_for_update()
        
    incident = inc_query.first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    unit = unit_query.first()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency unit not found.")

    # 2. Prevent Double Assignments
    if unit.status != "AVAILABLE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Unit {unit.callsign} is currently in '{unit.status}' status and cannot be dispatched."
        )

    # 3. Validate Incident State Transition
    try:
        validate_state_transition(incident.status, "DISPATCHED")
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 4. Atomic Status Transitions
    unit.status = "DISPATCHED"
    incident.status = "DISPATCHED"
    
    dispatcher = sanitize_actor_id(payload.dispatcher_id)
    dispatch_id = generate_uuid()

    assignment = DispatchAssignment(
        id=dispatch_id,
        incident_id=incident.id,
        unit_id=unit.id,
        dispatcher_id=dispatcher,
        status="DISPATCHED",
        notes=payload.notes or "Authorized by Dispatcher"
    )
    db.add(assignment)

    # 5. Immutable Audit Log Entry
    audit = AuditLog(
        incident_id=incident.id,
        actor=dispatcher,
        action="DISPATCH_APPROVED",
        details=json.dumps({
            "dispatch_id": dispatch_id,
            "unit_id": unit.id,
            "callsign": unit.callsign,
            "unit_type": unit.unit_type,
            "notes": payload.notes
        })
    )
    db.add(audit)
    
    db.commit()
    db.refresh(assignment)

    logger.info(f"Unit {unit.callsign} dispatched to incident {incident.incident_number} by {dispatcher}.")
    return assignment.to_dict()

@router.delete("/purge-all", status_code=status.HTTP_200_OK)
def purge_all_incidents(db: Session = Depends(get_db)):
    """
    Operator reset utility: clears all active incidents, dispatches, and logs,
    and returns all emergency response units to AVAILABLE status.
    """
    db.query(DispatchAssignment).delete()
    db.query(Incident).delete()
    db.query(AuditLog).delete()
    db.query(EmergencyUnit).update({EmergencyUnit.status: "AVAILABLE"})
    db.commit()
    logger.info("All incidents purged and units reset to AVAILABLE.")
    return {
        "status": "success",
        "message": "Incident queue purged. Portal is now empty and units are reset to AVAILABLE.",
        "incident_count": 0
    }
