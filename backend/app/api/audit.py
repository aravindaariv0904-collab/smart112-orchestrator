import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import asc
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.audit import AuditLog
from backend.app.models.incident import Incident

logger = logging.getLogger("smart112.api.audit")
router = APIRouter()


@router.get("/{incident_id}")
def get_incident_audit_trail(incident_id: str, db: Session = Depends(get_db)):
    """
    Returns the immutable chronological audit ledger records for a given incident ID.
    Enforces complete governance traceability.

    A non-existent incident returns 404 rather than an empty 200 so callers can tell
    "no events yet" apart from "wrong identifier".
    """
    incident_exists = (
        db.query(Incident.id).filter(Incident.id == incident_id).first() is not None
    )
    if not incident_exists and incident_id != "NO_ACTIVE_INCIDENT":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found.",
        )

    logs = (
        db.query(AuditLog)
        .filter(AuditLog.incident_id == incident_id)
        .order_by(asc(AuditLog.timestamp))
        .all()
    )
    return [log.to_dict() for log in logs]
