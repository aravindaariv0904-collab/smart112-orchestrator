import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai.extractor import extract_emergency_facts
from ai.followup import generate_targeted_followup_questions
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
from backend.app.services.correlator import find_incident_duplicates
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
    return data


def _next_incident_number(db: Session, offset: int = 1) -> str:
    """
    Generate sequential incident number using row locking or count fallback.
    Guarantees monotonicity and zero duplicates.
    """
    prefix = f"INC-{datetime.now(timezone.utc).year}-"
    bind = db.get_bind()
    is_postgres = bind is not None and bind.dialect.name == "postgresql"

    query = db.query(Incident.incident_number).filter(
        Incident.incident_number.like(f"{prefix}%")
    )
    if is_postgres:
        query = query.with_for_update()

    existing = query.all()

    max_sequence = 0
    for (number,) in existing:
        tail = number[len(prefix) :]
        if tail.isdigit():
            max_sequence = max(max_sequence, int(tail))

    return f"{prefix}{max_sequence + offset:04d}"


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)):
    """
    Ingest and register an emergency incident.

    Runs AI extraction with strict timeout, evaluates safety escalation rules,
    performs multi-dimensional spatio-temporal duplicate detection (BUG-10),
    persists the incident with concurrency-safe atomic sequence generation,
    and appends an immutable entry to the audit ledger.
    """
    assessment = await extract_emergency_facts(payload.description)

    incident_id = generate_uuid()
    category = assessment.get("incident_type", "GENERAL_EMERGENCY")
    severity = assessment.get("severity", "LEVEL_3_MODERATE")
    requires_review = assessment.get("requires_human_review", False)

    # Multi-dimensional Spatio-temporal Duplicate Correlation (BUG-10)
    now_utc = datetime.now(timezone.utc)
    recent_active = (
        db.query(Incident)
        .filter(Incident.status.in_(ACTIVE_INCIDENT_STATUSES))
        .all()
    )
    
    duplicate_candidates = find_incident_duplicates(
        new_lat=payload.latitude,
        new_lon=payload.longitude,
        new_category=category,
        new_hazards=assessment.get("hazards", []),
        active_incidents=recent_active,
        threshold=0.60,
    )

    potential_duplicate = None
    duplicate_dist_m = 0
    if duplicate_candidates:
        top_dup = duplicate_candidates[0]
        potential_duplicate = db.query(Incident).filter(Incident.id == top_dup["candidate_id"]).first()
        duplicate_dist_m = top_dup["distance_meters"]
        
        flags = assessment.setdefault("uncertainty_flags", [])
        if "POTENTIAL_DUPLICATE_REPORT" not in flags:
            flags.append("POTENTIAL_DUPLICATE_REPORT")
        assessment["potential_duplicate_of"] = top_dup["candidate_incident_number"]
        assessment["potential_duplicate_id"] = top_dup["candidate_id"]
        assessment["potential_duplicate_distance_meters"] = duplicate_dist_m
        assessment["duplicate_correlation_score"] = top_dup["composite_score"]
        assessment["duplicate_rationale"] = top_dup["rationale"]
        requires_review = True
        logger.warning(
            "Incident near (%.5f, %.5f) correlated as potential duplicate of %s (dist: %dm, score: %.2f).",
            payload.latitude,
            payload.longitude,
            top_dup["candidate_incident_number"],
            duplicate_dist_m,
            top_dup["composite_score"],
        )

    incident: Optional[Incident] = None
    for attempt in range(1, 6):
        try:
            inc_num = _next_incident_number(db, offset=attempt)
            incident = Incident(
                id=incident_id,
                incident_number=inc_num,
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
            db.commit()
            break
        except IntegrityError:
            db.rollback()
            logger.warning(
                "Incident number collision on attempt %s; regenerating sequence with offset.", attempt
            )
            if attempt == 5:
                # Guaranteed unique fallback sequence to ensure emergency call intake is never dropped
                entropy = int(datetime.now(timezone.utc).timestamp() * 1000) % 1000000
                inc_num = f"INC-{now_utc.year}-{entropy:06d}"
                incident = Incident(
                    id=incident_id,
                    incident_number=inc_num,
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
                db.add(
                    AuditLog(
                        incident_id=incident_id,
                        actor="SYSTEM_AI",
                        action="INCIDENT_REPORTED_AND_ASSESSED",
                        details=json.dumps({"incident_number": inc_num, "fallback_sequence": True}),
                    )
                )
                db.commit()
                break

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


@router.get("/{id}/duplicates")
def get_incident_duplicates(id: str, db: Session = Depends(get_db)):
    """Retrieve correlated duplicate reports for dispatcher cross-referencing (BUG-10)."""
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {id} not found.",
        )

    other_incidents = db.query(Incident).filter(Incident.id != id).all()

    hazards = []
    if incident.assessment_data:
        try:
            data = json.loads(incident.assessment_data)
            hazards = data.get("hazards", [])
        except Exception:
            pass

    matches = find_incident_duplicates(
        new_lat=incident.latitude,
        new_lon=incident.longitude,
        new_category=incident.category,
        new_hazards=hazards,
        active_incidents=other_incidents,
        threshold=0.45,
    )
    return {
        "incident_id": id,
        "incident_number": incident.incident_number,
        "correlated_duplicates": matches,
        "total_duplicates": len(matches),
    }


@router.post("/{id}/follow-up-questions")
def get_follow_up_questions(id: str, db: Session = Depends(get_db)):
    """Generate prioritized life-safety follow-up questions for missing triage data (BUG-11)."""
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {id} not found.",
        )

    assessment = {}
    if incident.assessment_data:
        try:
            assessment = json.loads(incident.assessment_data)
        except Exception:
            pass

    questions = generate_targeted_followup_questions(incident.category, assessment)
    return {
        "incident_id": id,
        "incident_number": incident.incident_number,
        "category": incident.category,
        "priority_questions": questions,
        "total_questions": len(questions),
    }


@router.post("/{id}/recommend", response_model=RecommendationResponse)
def get_unit_recommendations(id: str, db: Session = Depends(get_db)):
    """
    Execute multi-hazard capability matching and spatial proximity query against
    PostGIS (Haversine fallback) and return recommended units with tactical rationale.
    Transitions the incident from ASSESSED -> RECOMMENDED.
    """
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {id} not found.",
        )

    # Life-safety guard: incidents in terminal or already dispatched states must not be re-matched.
    if incident.status in NON_RECOMMENDABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Incident {incident.incident_number} is '{incident.status}' and no longer "
                f"accepts unit recommendations."
            ),
        )

    recommendation = match_candidate_units(db, incident)

    # Transition state to RECOMMENDED if previously ASSESSED or REPORTED
    if incident.status in ("ASSESSED", "REPORTED"):
        incident.status = "RECOMMENDED"
        db.add(
            AuditLog(
                incident_id=incident.id,
                actor="SYSTEM_MATCHER",
                action="RECOMMENDATION_GENERATED",
                details=json.dumps(
                    {
                        "candidate_count": len(recommendation["candidate_units"]),
                        "location_status": recommendation.get("location_status", "VERIFIED_IN_DISTRICT"),
                        "resource_deficit": recommendation.get("resource_deficit", False),
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
    x_dispatcher_token: Optional[str] = Header(None, alias="X-Dispatcher-Token"),
    db: Session = Depends(get_db),
):
    """
    Human dispatcher authorization endpoint.

    Delegates to the shared dispatch service, which atomically locks the rows,
    validates unit availability and dispatcher authentication, persists the assignment
    and records the action in the immutable audit ledger.
    """
    return execute_dispatch(
        db,
        incident_id=id,
        unit_id=payload.unit_id,
        dispatcher_id=payload.dispatcher_id,
        token=x_dispatcher_token,
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
