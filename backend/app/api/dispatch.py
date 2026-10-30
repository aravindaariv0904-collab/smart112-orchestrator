import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
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
    x_dispatcher_token: Optional[str] = Header(None, alias="X-Dispatcher-Token"),
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
        token=x_dispatcher_token,
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
    Authoritative responder telemetry endpoint per ARCHITECTURE.md specification.

    Applies the unit/incident state-machine rules atomically. Row locking prevents a
    race where two operators (or an automated poll) transition a unit concurrently.
    """
    normalized_status = payload.status.upper()
    if normalized_status == "RESOLVED":
        normalized_status = "AVAILABLE"

    if normalized_status not in VALID_UNIT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid unit status '{payload.status}'. Permitted values are: "
                f"{', '.join(sorted(VALID_UNIT_STATUSES))}."
            ),
        )

    # Lock unit first, matching the lock order in execute_dispatch to prevent deadlocks.
    unit = for_update(db.query(EmergencyUnit).filter(EmergencyUnit.id == id), db).first()
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency unit with ID '{id}' not found.",
        )

    # Unit cannot be set to DISPATCHED or ON_SCENE without a pre-existing assignment.
    # Allowing that would create "ghost" dispatches with no incident attached.
    active_assignment = (
        db.query(DispatchAssignment)
        .filter(
            DispatchAssignment.unit_id == unit.id,
            DispatchAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
        )
        .order_by(DispatchAssignment.timestamp.desc())
        .first()
    )

    if normalized_status in ASSIGNMENT_REQUIRED_STATUSES and not active_assignment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Unit {unit.callsign} has no active dispatch assignment. A unit cannot "
                f"transition to '{normalized_status}' without an authorized dispatch order."
            ),
        )

    # Check whether an active assignment should mirror this unit status update onto its incident.
    incident = None
    if active_assignment:
        incident = for_update(
            db.query(Incident).filter(Incident.id == active_assignment.incident_id), db
        ).first()

    old_status = unit.status
    unit.status = normalized_status
    unit.updated_at = datetime.now(timezone.utc)

    # Synchronise the attached incident with the field unit's lifecycle.
    incident_state_changed = False
    old_incident_status = None
    new_incident_status = None
    if incident:
        old_incident_status = incident.status
        if normalized_status == "ON_SCENE" and incident.status == "DISPATCHED":
            try:
                validate_state_transition(incident.status, "ON_SCENE")
                incident.status = "ON_SCENE"
                new_incident_status = "ON_SCENE"
                active_assignment.status = "ON_SCENE"
                incident_state_changed = True
            except InvalidStateTransitionError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        elif normalized_status == "AVAILABLE" and incident.status in ("DISPATCHED", "ON_SCENE"):
            try:
                validate_state_transition(incident.status, "RESOLVED")
                incident.status = "RESOLVED"
                new_incident_status = "RESOLVED"
                active_assignment.status = "COMPLETED"
                incident_state_changed = True
            except InvalidStateTransitionError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    actor = sanitize_actor_id(payload.dispatcher_id or unit.callsign)
    resolved_notes = payload.notes or f"Unit status updated from {old_status} to {normalized_status}"

    if incident:
        db.add(
            AuditLog(
                incident_id=incident.id,
                actor=actor,
                action=f"UNIT_STATUS_{normalized_status}",
                details=json.dumps(
                    {
                        "unit_id": unit.id,
                        "callsign": unit.callsign,
                        "old_status": old_status,
                        "new_status": normalized_status,
                        "incident_state_changed": incident_state_changed,
                        "old_incident_status": old_incident_status,
                        "new_incident_status": new_incident_status,
                        "notes": resolved_notes,
                    }
                ),
            )
        )

    db.commit()

    logger.info(
        "Unit %s transitioned %s -> %s (actor=%s, incident=%s)",
        unit.callsign,
        old_status,
        normalized_status,
        actor,
        incident.incident_number if incident else "none",
    )

    return {
        "status": "success",
        "unit": unit.to_dict(),
        "incident_status": incident.status if incident else None,
        "incident_state_changed": incident_state_changed,
    }
