import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai.extractor import extract_emergency_facts

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import generate_uuid
from backend.app.models.audit import AuditLog
from backend.app.models.dispatch import DispatchAssignment
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit
from backend.app.schemas.dispatch import (
    DispatchApprovalRequest,
    DispatchResponse,
    RecommendationResponse,
)
from backend.app.schemas.incident import IncidentCreate, IncidentResponse
from backend.app.services.dispatch_service import execute_dispatch
from backend.app.services.matcher import haversine_distance_km, match_candidate_units
from backend.app.services.state_machine import VALID_INCIDENT_STATUSES

logger = logging.getLogger("smart112.api.incidents")
router = APIRouter()

# Incidents in these states no longer accept new unit recommendations.
NON_RECOMMENDABLE_STATUSES = {"DISPATCHED", "ON_SCENE", "RESOLVED", "CANCELLED"}
ACTIVE_INCIDENT_STATUSES = {"REPORTED", "ASSESSED", "RECOMMENDED", "DISPATCHED"}


def _enrich_incident_dict(incident: Incident, db: Session) -> dict:
    """Enrich incident dictionary with active unit dispatch assignment telemetry."""
    data = incident.to_dict()
    assignment = (
        db.query(DispatchAssignment)
        .filter(
            DispatchAssignment.incident_id == incident.id,
            DispatchAssignment.status.in_(["DISPATCHED", "ON_SCENE"]),
        )
        .order_by(desc(DispatchAssignment.timestamp))
        .first()
    )
    if assignment:
        data["assigned_unit_id"] = assignment.unit_id
        unit = db.query(EmergencyUnit).filter(EmergencyUnit.id == assignment.unit_id).first()
        if unit:
            data["assigned_unit_callsign"] = unit.callsign
            data["assigned_unit_type"] = unit.unit_type
    else:
        data["assigned_unit_id"] = None
        data["assigned_unit_callsign"] = None
        data["assigned_unit_type"] = None
    return data


def _next_incident_number(db: Session) -> str:
    """
    Generate the next sequential incident number for the current UTC year.

    Parses existing numbers instead of relying on ``COUNT(*)`` so that deleting or
    purging incidents can never mint a duplicate primary key.
    """
    year = datetime.now(timezone.utc).year
    prefix = f"INC-{year}-"
    existing = (
        db.query(Incident.incident_number)
        .filter(Incident.incident_number.like(f"{prefix}%"))
        .all()
    )

    max_sequence = 0
    for (number,) in existing:
        tail = number[len(prefix) :]
        if tail.isdigit():
            max_sequence = max(max_sequence, int(tail))

    return f"{prefix}{max_sequence + 1:04d}"


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)):
    """
    Ingest and register an emergency incident.

    Runs AI extraction with a strict timeout, evaluates safety escalation rules,
    performs spatial-temporal duplicate detection (within 250m and 30m window),
    persists the incident and appends an immutable entry to the audit ledger.
    """
    assessment = await extract_emergency_facts(payload.description)

    incident_id = generate_uuid()
    category = assessment.get("incident_type", "GENERAL_EMERGENCY")
    severity = assessment.get("severity", "LEVEL_3_MODERATE")
    requires_review = assessment.get("requires_human_review", False)

    # Spatial-temporal duplicate check: query active incidents within 250m in the last 30 minutes
    now_utc = datetime.now(timezone.utc)
    recent_active = (
        db.query(Incident)
        .filter(Incident.status.in_(ACTIVE_INCIDENT_STATUSES))
        .all()
    )
    potential_duplicate = None
    duplicate_dist_m = 0
    for cand in recent_active:
        if cand.created_at:
            cand_time = cand.created_at
            if cand_time.tzinfo is None:
                cand_time = cand_time.replace(tzinfo=timezone.utc)
            if (now_utc - cand_time).total_seconds() > 1800:
                continue
        dist_km = haversine_distance_km(
            payload.latitude, payload.longitude, cand.latitude, cand.longitude
        )
        if dist_km <= 0.25:  # within 250 meters
            potential_duplicate = cand
            duplicate_dist_m = int(dist_km * 1000)
            break

    if potential_duplicate:
        flags = assessment.setdefault("uncertainty_flags", [])
        if "POTENTIAL_DUPLICATE_REPORT" not in flags:
            flags.append("POTENTIAL_DUPLICATE_REPORT")
        assessment["potential_duplicate_of"] = potential_duplicate.incident_number
        assessment["potential_duplicate_id"] = potential_duplicate.id
        assessment["potential_duplicate_distance_meters"] = duplicate_dist_m
        requires_review = True
        logger.warning(
            "Incident near (%.5f, %.5f) flagged as potential duplicate of %s (dist: %dm).",
            payload.latitude,
            payload.longitude,
            potential_duplicate.incident_number,
            duplicate_dist_m,
        )

    incident: Optional[Incident] = None
    for attempt in range(1, 4):
        incident = Incident(
            id=incident_id,
            incident_number=_next_incident_number(db),
            description=payload.description,
            category=category,
            status="ASSESSED",
            severity=severity,
            latitude=payload.latitude,
            longitude=payload.longitude,
            address=payload.address or "Location verified via coordinates",
            requires_human_review=requires_review,
            assessment_data=json.dumps(assessment),
        )
        db.add(incident)
        audit_details = {
            "incident_number": incident.incident_number,
            "category": category,
            "severity": severity,
            "requires_human_review": requires_review,
            "casualty_count": assessment.get("casualty_count", 0),
            "hazards": assessment.get("hazards", []),
            "missing_information": assessment.get("missing_information", []),
        }
        if potential_duplicate:
            audit_details["potential_duplicate_of"] = potential_duplicate.incident_number
            audit_details["potential_duplicate_distance_meters"] = duplicate_dist_m

        db.add(
            AuditLog(
                incident_id=incident_id,
                actor="SYSTEM_AI",
                action="INCIDENT_REPORTED_AND_ASSESSED",
                details=json.dumps(audit_details),
            )
        )
        try:
            db.commit()
            break
        except IntegrityError:
            # Two call-takers can ingest at the same instant; re-sequence and retry.
            db.rollback()
            logger.warning(
                "Incident number collision on attempt %s; regenerating sequence.", attempt
            )
            if attempt == 3:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Could not allocate a unique incident number. Please retry.",
                )

    db.refresh(incident)
    logger.info(
        "Incident %s created with severity %s. Audit logged.", incident.incident_number, severity
    )
    return _enrich_incident_dict(incident, db)


@router.get("", response_model=List[IncidentResponse])
def list_incidents(status_filter: Optional[str] = None, db: Session = Depends(get_db)):
    """Return active incidents sorted by severity priority and recency."""
    query = db.query(Incident)
    if status_filter:
        normalized = status_filter.strip().upper()
        if normalized not in VALID_INCIDENT_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid status filter '{status_filter}'. Permitted values are: "
                    f"{', '.join(sorted(VALID_INCIDENT_STATUSES))}."
                ),
            )
        query = query.filter(Incident.status == normalized)

    incidents = query.order_by(desc(Incident.created_at)).all()

    # Custom priority sorting: LEVEL_1_CRITICAL first.
    severity_order = {
        "LEVEL_1_CRITICAL": 0,
        "LEVEL_2_HIGH": 1,
        "LEVEL_3_MODERATE": 2,
        "LEVEL_4_LOW": 3,
    }
    incidents.sort(key=lambda item: severity_order.get(item.severity, 4))
    return [_enrich_incident_dict(incident, db) for incident in incidents]


@router.get("/{id}", response_model=IncidentResponse)
def get_incident(id: str, db: Session = Depends(get_db)):
    """Return details for a specific incident."""
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {id} not found.",
        )
    return _enrich_incident_dict(incident, db)


@router.post("/{id}/recommend", response_model=RecommendationResponse)
def get_unit_recommendations(id: str, db: Session = Depends(get_db)):
    """
    Execute the spatial proximity query against PostGIS (Haversine fallback) and
    return the top 3 recommended units with tactical rationale.
    Transitions the incident from ASSESSED -> RECOMMENDED.
    """
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    if incident.status in NON_RECOMMENDABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Incident {incident.incident_number} is '{incident.status}' and no longer "
                "accepts unit recommendations."
            ),
        )

    recommendation = match_candidate_units(db, incident, limit=3)

    if incident.status == "ASSESSED":
        incident.status = "RECOMMENDED"
        db.add(
            AuditLog(
                incident_id=incident.id,
                actor="SYSTEM_MATCHER",
                action="RECOMMENDATION_GENERATED",
                details=json.dumps(
                    {
                        "candidate_count": len(recommendation["candidate_units"]),
                        "top_unit": (
                            recommendation["candidate_units"][0]["callsign"]
                            if recommendation["candidate_units"]
                            else None
                        ),
                    }
                ),
            )
        )
        db.commit()

    return recommendation


@router.post("/{id}/approve-dispatch", response_model=DispatchResponse)
def approve_dispatch(
    id: str,
    payload: DispatchApprovalRequest,
    db: Session = Depends(get_db),
):
    """
    Human dispatcher authorization endpoint.

    Delegates to the shared dispatch service, which atomically locks the rows,
    validates unit availability and lifecycle state, persists the assignment and
    records the action in the immutable audit ledger.
    """
    return execute_dispatch(
        db,
        incident_id=id,
        unit_id=payload.unit_id,
        dispatcher_id=payload.dispatcher_id,
        notes=payload.notes,
        audit_action="DISPATCH_APPROVED",
        default_notes="Authorized by Dispatcher",
    )


@router.delete("/purge-all", status_code=status.HTTP_200_OK)
def purge_all_incidents(db: Session = Depends(get_db)):
    """
    Operator reset utility: clears incidents, dispatches and logs, and returns every
    emergency unit to AVAILABLE. Refused in production deployments.
    """
    if settings.is_production or not settings.ENABLE_DESTRUCTIVE_ENDPOINTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Destructive reset is disabled in this environment.",
        )

    try:
        # Delete children before parents to satisfy foreign keys.
        db.query(DispatchAssignment).delete()
        db.query(Incident).delete()
        db.query(AuditLog).delete()
        db.query(EmergencyUnit).update({EmergencyUnit.status: "AVAILABLE"})
        db.commit()
    except Exception:
        db.rollback()
        raise

    logger.info("All incidents purged and units reset to AVAILABLE.")
    return {
        "status": "success",
        "message": "Incident queue purged. Portal is now empty and units are reset to AVAILABLE.",
        "incident_count": 0,
    }
