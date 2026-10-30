import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ai.extractor import extract_emergency_facts
from ai.rules import evaluate_deterministic_rules
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit
from backend.app.services.matcher import is_unit_eligible, match_candidate_units

logger = logging.getLogger("smart112.orchestrator.agent_coordinator")


class TriageNLUAgent:
    """Agent 1: NLU extraction, hazard classification, and severity escalation."""
    name = "TriageNLUAgent"

    @staticmethod
    async def process(transcript: str) -> Dict[str, Any]:
        assessment = await extract_emergency_facts(transcript)
        return {
            "agent": TriageNLUAgent.name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "TRIAGE_COMPLETE",
            "assessment": assessment,
        }


class SpatialRoutingAgent:
    """Agent 2: Road-network circuity, dynamic traffic flow, and PostGIS fleet proximity."""
    name = "SpatialRoutingAgent"

    @staticmethod
    def process(
        db: Session,
        incident: Incident,
    ) -> Dict[str, Any]:
        recommendations = match_candidate_units(db, incident, limit=3)
        return {
            "agent": SpatialRoutingAgent.name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "ROUTING_COMPLETE",
            "recommendations": recommendations,
        }


class DispatcherSupervisorAgent:
    """Agent 3: Resource capability validation, RBAC verification, and mutual aid escalation."""
    name = "DispatcherSupervisorAgent"

    @staticmethod
    def process(
        triage_output: Dict[str, Any],
        routing_output: Dict[str, Any],
        dispatcher_callsign: str,
    ) -> Dict[str, Any]:
        from backend.app.core.security import is_authorized_dispatcher

        is_auth = is_authorized_dispatcher(dispatcher_callsign)
        recom = routing_output.get("recommendations", {})
        candidates = recom.get("candidate_units", [])
        has_deficit = recom.get("resource_deficit", False)

        top_unit = candidates[0] if candidates else None

        decision = "APPROVE_DISPATCH" if (is_auth and top_unit) else ("ESCALATE_MUTUAL_AID" if has_deficit else "REQUIRE_OPERATOR_REVIEW")

        return {
            "agent": DispatcherSupervisorAgent.name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "SUPERVISOR_EVALUATED",
            "dispatcher_callsign": dispatcher_callsign,
            "dispatcher_authorized": is_auth,
            "supervisory_decision": decision,
            "recommended_unit": top_unit,
            "resource_deficit": has_deficit,
            "rationale": recom.get("rationale", ""),
        }


async def run_coordinated_emergency_pipeline(
    db: Session,
    transcript: str,
    latitude: float,
    longitude: float,
    dispatcher_callsign: str = "DISPATCHER_GNT_01",
) -> Dict[str, Any]:
    """
    Executes the multi-agent emergency response intelligence pipeline (BUG-13).
    Coordinates: TriageNLUAgent -> SpatialRoutingAgent -> DispatcherSupervisorAgent.
    """
    pipeline_id = f"PIPE-{uuid.uuid4().hex[:8].upper()}"
    start_time = datetime.now(timezone.utc)

    # 1. Step 1: Triage
    triage_result = await TriageNLUAgent.process(transcript)
    assessment = triage_result["assessment"]

    # 2. Ephemeral Incident for spatial evaluation
    temp_incident = Incident(
        id=f"temp-{uuid.uuid4()}",
        incident_number=f"INC-{pipeline_id}",
        description=transcript,
        category=assessment.get("incident_type", "GENERAL_EMERGENCY"),
        status="ASSESSED",
        severity=assessment.get("severity", "LEVEL_2_HIGH"),
        latitude=latitude,
        longitude=longitude,
        requires_human_review=assessment.get("requires_human_review", False),
        assessment_data=str(assessment),
    )

    # 3. Step 2: Spatial Routing
    routing_result = SpatialRoutingAgent.process(db, temp_incident)

    # 4. Step 3: Dispatcher Supervisor Review
    supervisor_result = DispatcherSupervisorAgent.process(
        triage_result, routing_result, dispatcher_callsign
    )

    end_time = datetime.now(timezone.utc)
    elapsed_ms = round((end_time - start_time).total_seconds() * 1000, 1)

    return {
        "pipeline_id": pipeline_id,
        "status": "SUCCESS",
        "elapsed_ms": elapsed_ms,
        "coordination_agents": [
            TriageNLUAgent.name,
            SpatialRoutingAgent.name,
            DispatcherSupervisorAgent.name,
        ],
        "agent_trace": {
            "triage": triage_result,
            "spatial_routing": routing_result,
            "supervisor": supervisor_result,
        },
        "final_action_plan": {
            "decision": supervisor_result["supervisory_decision"],
            "primary_unit": supervisor_result["recommended_unit"],
            "resource_deficit": supervisor_result["resource_deficit"],
            "rationale": supervisor_result["rationale"],
        },
    }
