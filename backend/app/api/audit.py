import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import asc

from backend.app.core.database import get_db
from backend.app.models.audit import AuditLog

logger = logging.getLogger("smart112.api.audit")
router = APIRouter()

@router.get("/{incident_id}")
def get_incident_audit_trail(
    incident_id: str,
    db: Session = Depends(get_db)
):
    """
    Returns the immutable chronological audit ledger records for a given incident ID.
    Enforces complete governance traceability.
    """
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.incident_id == incident_id)
        .order_by(asc(AuditLog.timestamp))
        .all()
    )
    return [log.to_dict() for log in logs]
