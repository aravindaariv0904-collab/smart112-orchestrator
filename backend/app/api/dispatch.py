import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import generate_uuid, sanitize_actor_id
from backend.app.models.unit import EmergencyUnit
from backend.app.models.incident import Incident
from backend.app.models.dispatch import DispatchAssignment
from backend.app.models.audit import AuditLog
from backend.app.schemas.dispatch import (
    UnitStatusUpdate,
    DispatchConfirmationRequest,
    DispatchResponse
)
from backend.app.services.state_machine import validate_state_transition, InvalidStateTransitionError

logger = logging.getLogger("smart112.api.dispatch")
router = APIRouter()

@router.get("/units")
def list_units(
    unit_type: Optional[str] = None,
    unit_status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Returns all emergency response units with real-time locations and readiness status."""
    query = db.query(EmergencyUnit)
    if unit_type:
        query = query.filter(EmergencyUnit.unit_type == unit_type.upper())
    if unit_status:
        query = query.filter(EmergencyUnit.status == unit_status.upper())
    units = query.all()
    return [u.to_dict() for u in units]

@router.post("/dispatch/confirm", response_model=DispatchResponse, status_code=status.HTTP_200_OK)
def confirm_dispatch(
    payload: DispatchConfirmationRequest,
    db: Session = Depends(get_db)
):
    """
    Authoritative dispatch confirmation endpoint per ARCHITECTURE.md specification.
    Atomically locks and validates unit availability, transitions incident to DISPATCHED,
    creates dispatch assignment, and records the action into the immutable audit ledger.
    """
    is_sqlite = db.bind.dialect.name == "sqlite" if db.bind else False
    inc_query = db.query(Incident).filter(Incident.id == payload.incident_id)
    unit_query = db.query(EmergencyUnit).filter(EmergencyUnit.id == payload.unit_id)
    if not is_sqlite:
        inc_query = inc_query.with_for_update()
        unit_query = unit_query.with_for_update()

    incident = inc_query.first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{payload.incident_id}' not found."
        )

    unit = unit_query.first()
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency unit with ID '{payload.unit_id}' not found."
        )

    # Prevent double assignments on already dispatched or busy units
    if unit.status != "AVAILABLE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Unit {unit.callsign} is currently in '{unit.status}' status and cannot be dispatched."
        )

    # Validate state transition
    try:
        validate_state_transition(incident.status, "DISPATCHED")
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Atomic state updates
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
        notes=payload.notes or "Authorized via Dispatch Gateway"
    )
    db.add(assignment)

    # Append to immutable audit log
    audit = AuditLog(
        incident_id=incident.id,
        actor=dispatcher,
        action="DISPATCH_CONFIRMED",
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

    logger.info(f"Unit {unit.callsign} confirmed dispatched to incident {incident.incident_number} by {dispatcher}.")
    return assignment.to_dict()

@router.patch("/units/{id}/status")
def update_unit_status(
    id: str,
    payload: UnitStatusUpdate,
    db: Session = Depends(get_db)
):
    """
    Updates the operational lifecycle state of an emergency unit (e.g. DISPATCHED -> ON_SCENE -> AVAILABLE).
    When a unit is released back to AVAILABLE, any associated active incident transitions to RESOLVED.
    All actions append to the immutable AuditLog.
    """
    unit = db.query(EmergencyUnit).filter(EmergencyUnit.id == id).first()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency unit not found.")

    target_status = payload.status.upper()
    actor = sanitize_actor_id(payload.dispatcher_id)
    old_status = unit.status

    # Locate active assignment for this unit
    active_assignment = (
        db.query(DispatchAssignment)
        .filter(
            DispatchAssignment.unit_id == unit.id,
            DispatchAssignment.status.in_(["DISPATCHED", "ON_SCENE"])
        )
        .order_by(DispatchAssignment.timestamp.desc())
        .first()
    )

    incident_id = active_assignment.incident_id if active_assignment else "NO_ACTIVE_INCIDENT"
    associated_incident = db.query(Incident).filter(Incident.id == incident_id).first() if active_assignment else None

    # Handle transitions
    if target_status == "ON_SCENE":
        unit.status = "ON_SCENE"
        if active_assignment:
            active_assignment.status = "ON_SCENE"
            active_assignment.on_scene_at = datetime.now(timezone.utc)
        if associated_incident:
            try:
                validate_state_transition(associated_incident.status, "ON_SCENE")
                associated_incident.status = "ON_SCENE"
            except InvalidStateTransitionError as e:
                logger.warning(f"Incident transition error: {e}")

    elif target_status in ["AVAILABLE", "RESOLVED"]:
        unit.status = "AVAILABLE"
        if active_assignment:
            active_assignment.status = "COMPLETED"
            active_assignment.cleared_at = datetime.now(timezone.utc)
        if associated_incident:
            try:
                validate_state_transition(associated_incident.status, "RESOLVED")
                associated_incident.status = "RESOLVED"
            except InvalidStateTransitionError as e:
                logger.warning(f"Incident transition error: {e}")
    else:
        unit.status = target_status

    # Record Audit Entry
    audit = AuditLog(
        incident_id=incident_id,
        actor=actor,
        action=f"UNIT_STATUS_{target_status}",
        details=json.dumps({
            "unit_id": unit.id,
            "callsign": unit.callsign,
            "previous_status": old_status,
            "new_status": unit.status,
            "incident_status": associated_incident.status if associated_incident else None,
            "notes": payload.notes
        })
    )
    db.add(audit)
    db.commit()
    db.refresh(unit)

    return {
        "unit": unit.to_dict(),
        "incident_status": associated_incident.status if associated_incident else None,
        "message": f"Unit {unit.callsign} updated from {old_status} to {unit.status}."
    }
