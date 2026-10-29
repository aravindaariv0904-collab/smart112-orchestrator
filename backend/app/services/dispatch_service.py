import json
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.security import generate_uuid, sanitize_actor_id
from backend.app.models.audit import AuditLog
from backend.app.models.dispatch import DispatchAssignment
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit
from backend.app.services.state_machine import (
    InvalidStateTransitionError,
    validate_state_transition,
)

logger = logging.getLogger("smart112.services.dispatch")


def _for_update(query, db: Session):
    """Apply SELECT ... FOR UPDATE where the dialect supports row locking."""
    if db.bind is not None and db.bind.dialect.name != "sqlite":
        return query.with_for_update()
    return query


def execute_dispatch(
    db: Session,
    *,
    incident_id: str,
    unit_id: str,
    dispatcher_id: str,
    notes: Optional[str],
    audit_action: str,
    default_notes: str,
) -> DispatchAssignment:
    """
    Single authoritative dispatch routine shared by every dispatch entry point.

    Atomically locks the incident and unit rows, rejects double-booking, validates the
    incident state machine, persists the assignment and appends the audit ledger entry.
    """
    incident = _for_update(db.query(Incident).filter(Incident.id == incident_id), db).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found.",
        )

    unit = _for_update(db.query(EmergencyUnit).filter(EmergencyUnit.id == unit_id), db).first()
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency unit with ID '{unit_id}' not found.",
        )

    # Prevent double assignments on already dispatched or busy units.
    if unit.status != "AVAILABLE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Unit {unit.callsign} is currently in '{unit.status}' status and cannot be dispatched.",
        )

    try:
        validate_state_transition(incident.status, "DISPATCHED")
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    dispatcher = sanitize_actor_id(dispatcher_id)
    dispatch_id = generate_uuid()
    resolved_notes = notes or default_notes

    unit.status = "DISPATCHED"
    incident.status = "DISPATCHED"

    assignment = DispatchAssignment(
        id=dispatch_id,
        incident_id=incident.id,
        unit_id=unit.id,
        dispatcher_id=dispatcher,
        status="DISPATCHED",
        notes=resolved_notes,
    )
    db.add(assignment)

    db.add(
        AuditLog(
            incident_id=incident.id,
            actor=dispatcher,
            action=audit_action,
            details=json.dumps(
                {
                    "dispatch_id": dispatch_id,
                    "unit_id": unit.id,
                    "callsign": unit.callsign,
                    "unit_type": unit.unit_type,
                    "notes": notes,
                }
            ),
        )
    )

    try:
        db.commit()
    except IntegrityError as exc:  # pragma: no cover - defensive against concurrent writers
        db.rollback()
        logger.error("Dispatch commit failed for incident %s: %s", incident_id, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dispatch conflict detected. Reload the incident and retry.",
        )

    db.refresh(assignment)
    logger.info(
        "Unit %s dispatched to incident %s by %s.",
        unit.callsign,
        incident.incident_number,
        dispatcher,
    )
    return assignment.to_dict()
