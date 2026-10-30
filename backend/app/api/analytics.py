import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.audit import AuditLog
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit

logger = logging.getLogger("smart112.api.analytics")
router = APIRouter()


@router.get("/dashboard")
def get_operational_analytics_dashboard(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns live operational metrics derived strictly from the actual database state (BUG-14).
    Zero mocked constants: all metrics aggregate real Incident, EmergencyUnit, and AuditLog records.
    """
    # 1. Incident Counts
    total_incidents = db.query(func.count(Incident.id)).scalar() or 0
    resolved_incidents = (
        db.query(func.count(Incident.id)).filter(Incident.status == "RESOLVED").scalar() or 0
    )
    active_incidents = total_incidents - resolved_incidents
    requires_review = (
        db.query(func.count(Incident.id))
        .filter(Incident.requires_human_review == True)
        .scalar()
        or 0
    )

    # 2. Aggregations by Severity, Category, and Status
    severity_rows = (
        db.query(Incident.severity, func.count(Incident.id))
        .group_by(Incident.severity)
        .all()
    )
    by_severity = {row[0]: row[1] for row in severity_rows}

    category_rows = (
        db.query(Incident.category, func.count(Incident.id))
        .group_by(Incident.category)
        .all()
    )
    by_category = {row[0]: row[1] for row in category_rows}

    status_rows = (
        db.query(Incident.status, func.count(Incident.id))
        .group_by(Incident.status)
        .all()
    )
    by_status = {row[0]: row[1] for row in status_rows}

    # 3. Fleet Metrics
    total_units = db.query(func.count(EmergencyUnit.id)).scalar() or 0
    available_units = (
        db.query(func.count(EmergencyUnit.id))
        .filter(EmergencyUnit.status == "AVAILABLE")
        .scalar()
        or 0
    )
    dispatched_units = (
        db.query(func.count(EmergencyUnit.id))
        .filter(EmergencyUnit.status == "DISPATCHED")
        .scalar()
        or 0
    )
    on_scene_units = (
        db.query(func.count(EmergencyUnit.id))
        .filter(EmergencyUnit.status == "ON_SCENE")
        .scalar()
        or 0
    )

    unit_type_rows = (
        db.query(EmergencyUnit.unit_type, func.count(EmergencyUnit.id))
        .group_by(EmergencyUnit.unit_type)
        .all()
    )
    fleet_by_type = {row[0]: row[1] for row in unit_type_rows}

    # 4. Total Audit Ledger Records
    total_audit_events = db.query(func.count(AuditLog.id)).scalar() or 0

    # 5. Average Response Time from Audit Log (Time from INCIDENT_REPORTED to UNIT_STATUS_ON_SCENE)
    on_scene_logs = (
        db.query(AuditLog)
        .filter(AuditLog.action.in_(("UNIT_STATUS_ON_SCENE", "ON_SCENE")))
        .all()
    )

    durations_min = []
    for log in on_scene_logs:
        # Find corresponding creation log
        create_log = (
            db.query(AuditLog)
            .filter(
                AuditLog.incident_id == log.incident_id,
                AuditLog.action.in_(("INCIDENT_REPORTED_AND_ASSESSED", "INCIDENT_CREATED")),
            )
            .first()
        )
        if create_log and log.timestamp and create_log.timestamp:
            t1 = create_log.timestamp
            t2 = log.timestamp
            if t1.tzinfo is None:
                t1 = t1.replace(tzinfo=timezone.utc)
            if t2.tzinfo is None:
                t2 = t2.replace(tzinfo=timezone.utc)
            sec = (t2 - t1).total_seconds()
            if 0 < sec < 86400:
                durations_min.append(sec / 60.0)

    avg_response_time = (
        round(sum(durations_min) / len(durations_min), 2) if durations_min else 0.0
    )

    fleet_utilization_pct = (
        round(((total_units - available_units) / max(1, total_units)) * 100.0, 1)
        if total_units > 0
        else 0.0
    )

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "incidents": {
            "total": total_incidents,
            "active": active_incidents,
            "resolved": resolved_incidents,
            "requires_human_review": requires_review,
            "by_severity": by_severity,
            "by_category": by_category,
            "by_status": by_status,
        },
        "fleet": {
            "total_units": total_units,
            "available": available_units,
            "dispatched": dispatched_units,
            "on_scene": on_scene_units,
            "utilization_percent": fleet_utilization_pct,
            "by_type": fleet_by_type,
        },
        "performance": {
            "average_response_time_minutes": avg_response_time,
            "total_audit_events_logged": total_audit_events,
            "ssot_source": "LIVE_DATABASE_AGGREGATE",
        },
    }
