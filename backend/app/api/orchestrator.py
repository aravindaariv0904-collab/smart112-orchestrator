import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from orchestrator.agent_coordinator import run_coordinated_emergency_pipeline

logger = logging.getLogger("smart112.api.orchestrator")
router = APIRouter()


class OrchestratorWorkflowRequest(BaseModel):
    transcript: str = Field(..., min_length=3, description="Emergency call text or transcript")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    dispatcher_callsign: Optional[str] = "DISPATCHER_GNT_01"


@router.post("/triage-workflow")
async def execute_multi_agent_workflow(
    payload: OrchestratorWorkflowRequest,
    db: Session = Depends(get_db),
):
    """
    Executes the coordinated multi-agent emergency response intelligence pipeline (BUG-13).
    Chains TriageNLUAgent -> SpatialRoutingAgent -> DispatcherSupervisorAgent.
    """
    try:
        result = await run_coordinated_emergency_pipeline(
            db=db,
            transcript=payload.transcript,
            latitude=payload.latitude,
            longitude=payload.longitude,
            dispatcher_callsign=payload.dispatcher_callsign or "DISPATCHER_GNT_01",
        )
        return result
    except Exception as exc:
        logger.error("Multi-agent orchestrator failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent coordination workflow failed: {str(exc)}",
        )
