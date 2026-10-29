import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import sanitize_actor_id
from backend.app.models.audit import AuditLog
from backend.app.models.dispatch import DispatchAssignment
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit
from backend.app.schemas.dispatch import (
    DispatchConfirmationRequest,
    DispatchResponse,
    UnitStatusUpdate,
)
from backend.app.services.dispatch_service import execute_dispatch, for_update
from backend.app.services.state_machine import (
    InvalidStateTransitionError,
    validate_state_transition,
)

logger = logging.getLogger("smart112.api.dispatch")
router = APIRouter()

# Canonical unit lifecycle states. RESOLVED is accepted as an operator alias for
# AVAILABLE so that mobile terminals can signal "cleared" with a single tap.
VALID_UNIT_STATUSES = {"AVAILABLE", "DISPATCHED", "ON_SCENE", "RESOLVED"}
ACTIVE_ASSIGNMENT_STATUSES = ("DISPATCHED", "ON_SCENE")
# States that can only ever be reached while the unit holds a live assignment.
ASSIGNMENT_REQUIRED_STATUSES = {"DISPATCHED", "ON_SCENE"}


@router.get("/units")
def list_units(
    unit_type: Optional[str] = None,
    unit_status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return all emergency response units with real-time locations and readiness status."""
    query = db.query(EmergencyUnit)
    if unit_type:
        query = query.filter(EmergencyUnit.unit_type == unit_type.upper())
    if unit_status:
        query = query.filter(EmergencyUnit.status == unit_status.upper())
    units = query.all()
    return [unit.to_dict() for unit in units]


@router.post("/dispatch/confirm", response_model=DispatchResponse, status_code=status.HTTP_200_OK)
def confirm_dispatch(
    payload: DispatchConfirmationRequest,
    db: Session = Depends(get_db),
):
    """
    Authoritative dispatch confirmation endpoint per ARCHITECTURE.md specification.
    Locks the unit, validates availability and lifecycle state, then records the
    assignment and audit entry through the shared dispatch service.
    """
    return execute_dispatch(
        db,
        incident_id=payload.incident_id,
        unit_id=payload.unit_id,
        dispatcher_id=payload.dispatcher_id,
        notes=payload.notes,
        audit_action="DISPATCH_CONFIRMED",
        default_notes="Authorized via Dispatch Gateway",
    )


@router.patch("/units/{id}/status")
def update_unit_status(
    id: str,
    payload: UnitStatusUpdate,
    db: Session = Depends(get_db),
):
    """
    Update the operational lifecycle state of an emergency unit
    (DISPATCHED -> ON_SCENE -> AVAILABLE/RESOLVED).

    Releasing a unit back to AVAILABLE closes its active assignment and resolves the
    associated incident. Every change appends an immutable AuditLog entry.

    Rows are locked unit -> assignment -> incident, the same order used by
    ``execute_dispatch``, so concurrent dispatch and field updates cannot deadlock.
    """
    unit = for_update(db.query(EmergencyUnit).filter(EmergencyUnit.id == id), db).first()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency unit not found.")

    target_status = (payload.status or "").strip().upper()
    if target_status not in VALID_UNIT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid unit status '{target_status}'. "
                f"Permitted statuses are: {', '.join(sorted(VALID_UNIT_STATUSES))}."
            ),
        )

    actor = sanitize_actor_id(payload.dispatcher_id)
    previous_status = unit.status

    # Locate the active assignment for this unit (if any).
    active_assignment = for_update(
        db.query(DispatchAssignment).filter(
            DispatchAssignment.unit_id == unit.id,
            DispatchAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
        ),
        db,
    ).order_by(DispatchAssignment.timestamp.desc()).first()

    # A unit cannot be moved into a busy state unless it actually holds a task.
    # Without this guard a stale MDT tap could mark an idle ambulance ON_SCENE and
    # silently strand it (no assignment exists to ever clear it again).
    if target_status in ASSIGNMENT_REQUIRED_STATUSES and not active_assignment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Unit {unit.callsign} has no active dispatch assignment and cannot be "
                f"moved to '{target_status}'."
            ),
        )

    associated_incident = None
    if active_assignment:
        associated_incident = for_update(
            db.query(Incident).filter(Incident.id == active_assignment.incident_id), db
        ).first()
    audit_incident_id = associated_incident.id if associated_incident else "NO_ACTIVE_INCIDENT"

    skipped_transition = None

    # Apply the unit + assignment + incident transitions.
    if target_status == "ON_SCENE":
        unit.status = "ON_SCENE"
        active_assignment.status = "ON_SCENE"
        if not active_assignment.on_scene_at:
            active_assignment.on_scene_at = datetime.now(timezone.utc)
        if associated_incident:
            try:
                validate_state_transition(associated_incident.status, "ON_SCENE")
                associated_incident.status = "ON_SCENE"
            except InvalidStateTransitionError as exc:
                skipped_transition = str(exc)
                logger.warning(
                    "Incident transition skipped for unit %s: %s", unit.callsign, exc
                )

    elif target_status in ("AVAILABLE", "RESOLVED"):
        unit.status = "AVAILABLE"
        if active_assignment:
            active_assignment.status = "COMPLETED"
            if not active_assignment.cleared_at:
                active_assignment.cleared_at = datetime.now(timezone.utc)
        if associated_incident:
            try:
                validate_state_transition(associated_incident.status, "RESOLVED")
                associated_incident.status = "RESOLVED"
            except InvalidStateTransitionError as exc:
                skipped_transition = str(exc)
                logger.warning(
                    "Incident transition skipped for unit %s: %s", unit.callsign, exc
                )

    else:  # DISPATCHED (manual override / re-task of a live assignment)
        unit.status = "DISPATCHED"
        active_assignment.status = "DISPATCHED"

    db.add(
        AuditLog(
            incident_id=audit_incident_id,
            actor=actor,
            action=f"UNIT_STATUS_{target_status}",
            details=json.dumps(
                {
                    "unit_id": unit.id,
                    "callsign": unit.callsign,
                    "previous_status": previous_status,
                    "new_status": unit.status,
                    "assignment_id": active_assignment.id if active_assignment else None,
                    "incident_status": associated_incident.status if associated_incident else None,
                    "skipped_transition": skipped_transition,
                    "notes": payload.notes,
                }
            ),
        )
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(unit)

    return {
        "unit": unit.to_dict(),
        "incident_status": associated_incident.status if associated_incident else None,
        "message": f"Unit {unit.callsign} updated from {previous_status} to {unit.status}.",
    }
