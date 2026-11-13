"""
AI Agent Execution Tracking API

Provides endpoints for:
- Tracking AI agent executions and their lifecycle
- Recording execution traces and steps
- Monitoring agent performance and latency
- Managing agent configurations
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from backend.app.core.database import get_db, Session
from backend.app.models.aitracking import AgentExecution, AgentTrace
from backend.app.services.spatial import haversine_distance

logger = logging.getLogger("smart112.api.aitracking")
router = APIRouter(prefix="/api/v1/ai/tracking", tags=["ai-tracking"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class AgentExecutionStart(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=200)
    agent_type: str = Field(..., max_length=100, description="Type of agent (e.g., 'incident_classifier', 'resource_matcher')")
    trigger: str = Field(default="API", pattern=r"^(API|EVENT|SCHEDULE|MANUAL)$")
    session_id: Optional[str] = Field(None, max_length=100)
    input_data: Dict[str, Any] = Field(default={}, description="Input data for the agent")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    parent_execution_id: Optional[str] = Field(None, max_length=100, description="Parent execution for nested agents")
    tags: Optional[List[str]] = Field(default_factory=list)

class AgentExecutionResponse(BaseModel):
    id: str
    agent_name: str
    agent_type: str
    trigger: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    input_summary: Dict[str, Any]
    output_summary: Optional[Dict[str, Any]]
    tags: List[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    # Relationships
    parent_id: Optional[str]
    root_id: Optional[str]
    trace_count: int = 0

    class Config:
        from_attributes = True

class AgentTraceCreate(BaseModel):
    execution_id: str = Field(..., max_length=100)
    step_number: int = Field(..., ge=0)
    step_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    status: str = Field(default="COMPLETED", pattern=r"^(PENDING|RUNNING|COMPLETED|FAILED|SKIPPED)$")
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = Field(None, ge=0)
    error_message: Optional[str] = Field(None, max_length=2000)
    metadata: Optional[Dict[str, Any]] = None

class AgentTraceResponse(BaseModel):
    id: str
    execution_id: str
    step_number: int
    step_name: str
    description: Optional[str]
    status: str
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    latency_ms: Optional[int]
    error_message: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True

class AgentTraceUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern=r"^(PENDING|RUNNING|COMPLETED|FAILED|SKIPPED)$")
    output_data: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = Field(None, ge=0)
    error_message: Optional[str] = Field(None, max_length=2000)
    metadata: Optional[Dict[str, Any]] = None

class AgentExecutionUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern=r"^(PENDING|RUNNING|COMPLETED|FAILED|TERMINATED)$")
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = Field(None, max_length=2000)


# =============================================================================
# Execution Endpoints
# =============================================================================

@router.post("/executions", response_model=AgentExecutionResponse, status_code=status.HTTP_201_CREATED)
def start_execution(
    payload: AgentExecutionStart,
    db: Session = Depends(get_db),
):
    """
    Start a new AI agent execution.
    
    Creates an execution record and returns the execution ID.
    The agent should update its status as it progresses through steps.
    """
    # Determine root execution ID
    root_id = payload.parent_execution_id
    if not root_id:
        root_id = f"root-{datetime.now(timezone.utc).timestamp()}"
    
    execution = AgentExecution(
        id=f"exec-{datetime.now(timezone.utc).timestamp()}-{hash(payload.agent_name) % 10000}",
        agent_name=payload.agent_name,
        agent_type=payload.agent_type,
        trigger=payload.trigger,
        status="PENDING",
        input_data=payload.input_data,
        execution_metadata=payload.metadata or {},
        parent_execution_id=payload.parent_execution_id,
        root_execution_id=root_id,
        tags=payload.tags or [],
    )
    
    db.add(execution)
    db.commit()
    db.refresh(execution)
    
    logger.info(
        "Started AI execution: %s (type: %s, id: %s)",
        payload.agent_name,
        payload.agent_type,
        execution.id
    )
    
    return {
        "id": execution.id,
        "agent_name": execution.agent_name,
        "agent_type": execution.agent_type,
        "trigger": execution.trigger,
        "status": execution.status,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "duration_ms": execution.duration_ms,
        "input_summary": execution.input_summary,
        "output_summary": execution.output_summary,
        "tags": execution.tags,
        "error_message": execution.error_message,
        "created_at": execution.created_at,
        "updated_at": execution.updated_at,
        "parent_id": execution.parent_execution_id,
        "root_id": execution.root_execution_id,
        "trace_count": 0,
    }


@router.get("/executions", response_model=List[AgentExecutionResponse])
def list_executions(
    agent_name: Optional[str] = Query(None, max_length=200),
    agent_type: Optional[str] = Query(None, max_length=100),
    status: Optional[str] = Query(None, pattern=r"^(PENDING|RUNNING|COMPLETED|FAILED|TERMINATED)$"),
    trigger: Optional[str] = Query(None, pattern=r"^(API|EVENT|SCHEDULE|MANUAL)$"),
    from_time: Optional[datetime] = Query(None),
    to_time: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List agent executions with filtering.
    
    Supports filtering by:
    - Agent name or type
    - Execution status
    - Trigger source
    - Time range
    """
    query = db.query(AgentExecution)
    
    if agent_name:
        query = query.filter(AgentExecution.agent_name.ilike(f"%{agent_name}%"))
    if agent_type:
        query = query.filter(AgentExecution.agent_type == agent_type)
    if status:
        query = query.filter(AgentExecution.status == status)
    if trigger:
        query = query.filter(AgentExecution.trigger == trigger)
    if from_time:
        query = query.filter(AgentExecution.created_at >= from_time)
    if to_time:
        query = query.filter(AgentExecution.created_at <= to_time)
    
    executions = query.order_by(AgentExecution.created_at.desc()).offset(offset).limit(limit).all()
    
    result = []
    for exec in executions:
        trace_count = db.query(AgentTrace).filter(
            AgentTrace.execution_id == exec.id
        ).count()
        
        result.append({
            "id": exec.id,
            "agent_name": exec.agent_name,
            "agent_type": exec.agent_type,
            "trigger": exec.trigger,
            "status": exec.status,
            "started_at": exec.started_at,
            "completed_at": exec.completed_at,
            "duration_ms": exec.duration_ms,
            "input_summary": exec.input_summary,
            "output_summary": exec.output_summary,
            "tags": exec.tags,
            "error_message": exec.error_message,
            "created_at": exec.created_at,
            "updated_at": exec.updated_at,
            "parent_id": exec.parent_execution_id,
            "root_id": exec.root_execution_id,
            "trace_count": trace_count,
        })
    
    return result


@router.get("/executions/{execution_id}", response_model=AgentExecutionResponse)
def get_execution(
    execution_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific agent execution by ID."""
    execution = db.query(AgentExecution).filter(
        AgentExecution.id == execution_id
    ).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    trace_count = db.query(AgentTrace).filter(
        AgentTrace.execution_id == execution_id
    ).count()
    
    return {
        "id": execution.id,
        "agent_name": execution.agent_name,
        "agent_type": execution.agent_type,
        "trigger": execution.trigger,
        "status": execution.status,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "duration_ms": execution.duration_ms,
        "input_summary": execution.input_summary,
        "output_summary": execution.output_summary,
        "tags": execution.tags,
        "error_message": execution.error_message,
        "created_at": execution.created_at,
        "updated_at": execution.updated_at,
        "parent_id": execution.parent_execution_id,
        "root_id": execution.root_execution_id,
        "trace_count": trace_count,
    }


@router.put("/executions/{execution_id}", response_model=AgentExecutionResponse)
def update_execution(
    execution_id: str,
    payload: AgentExecutionUpdate,
    db: Session = Depends(get_db),
):
    """Update an agent execution's status or output."""
    execution = db.query(AgentExecution).filter(
        AgentExecution.id == execution_id
    ).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    if payload.status:
        execution.status = payload.status
        if payload.status == "RUNNING" and not execution.started_at:
            execution.started_at = datetime.now(timezone.utc)
        elif payload.status in ["COMPLETED", "FAILED", "TERMINATED"]:
            if not execution.completed_at:
                execution.completed_at = datetime.now(timezone.utc)
            # Calculate duration
            if execution.started_at and execution.completed_at:
                duration = (execution.completed_at - execution.started_at).total_seconds() * 1000
                execution.duration_ms = int(duration)
    
    if payload.output_data is not None:
        execution.output_data = payload.output_data
        execution.output_summary = {
            "keys": list(payload.output_data.keys()) if payload.output_data else [],
            "record_count": len(payload.output_data.get("results", [])) if payload.output_data else 0,
        }
    
    if payload.error_message is not None:
        execution.error_message = payload.error_message
    
    execution.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(execution)
    
    logger.info(
        "Updated execution %s: status=%s",
        execution_id,
        execution.status
    )
    
    return {
        "id": execution.id,
        "agent_name": execution.agent_name,
        "agent_type": execution.agent_type,
        "trigger": execution.trigger,
        "status": execution.status,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "duration_ms": execution.duration_ms,
        "input_summary": execution.input_summary,
        "output_summary": execution.output_summary,
        "tags": execution.tags,
        "error_message": execution.error_message,
        "created_at": execution.created_at,
        "updated_at": execution.updated_at,
        "parent_id": execution.parent_execution_id,
        "root_id": execution.root_execution_id,
        "trace_count": db.query(AgentTrace).filter(AgentTrace.execution_id == execution_id).count(),
    }


@router.delete("/executions/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_execution(
    execution_id: str,
    db: Session = Depends(get_db),
):
    """Delete an agent execution and its traces."""
    execution = db.query(AgentExecution).filter(
        AgentExecution.id == execution_id
    ).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    # Delete associated traces first
    db.query(AgentTrace).filter(
        AgentTrace.execution_id == execution_id
    ).delete()
    
    db.delete(execution)
    db.commit()
    
    logger.info("Deleted execution: %s", execution_id)
    return None


# =============================================================================
# Trace Endpoints
# =============================================================================

@router.post("/executions/{execution_id}/traces", response_model=AgentTraceResponse, status_code=status.HTTP_201_CREATED)
def add_trace(
    execution_id: str,
    payload: AgentTraceCreate,
    db: Session = Depends(get_db),
):
    """
    Add a trace step to an execution.
    
    Records a step within an agent execution, useful for:
    - Monitoring long-running agents
    - Debugging failed executions
    - Performance analysis
    """
    # Verify execution exists
    execution = db.query(AgentExecution).filter(
        AgentExecution.id == execution_id
    ).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    # Auto-start execution if not started
    if execution.status == "PENDING":
        execution.status = "RUNNING"
        execution.started_at = datetime.now(timezone.utc)
        db.commit()
    
    trace = AgentTrace(
        id=f"trace-{execution_id}-{payload.step_number}-{datetime.now(timezone.utc).timestamp()}",
        execution_id=execution_id,
        step_number=payload.step_number,
        step_name=payload.step_name,
        description=payload.description,
        status=payload.status,
        input_data=payload.input_data,
        output_data=payload.output_data,
        latency_ms=payload.latency_ms,
        error_message=payload.error_message,
        metadata=payload.metadata,
    )
    
    db.add(trace)
    db.commit()
    db.refresh(trace)
    
    logger.debug(
        "Added trace step %d to execution %s: %s",
        payload.step_number,
        execution_id,
        payload.step_name
    )
    
    return {
        "id": trace.id,
        "execution_id": trace.execution_id,
        "step_number": trace.step_number,
        "step_name": trace.step_name,
        "description": trace.description,
        "status": trace.status,
        "input_data": trace.input_data,
        "output_data": trace.output_data,
        "latency_ms": trace.latency_ms,
        "error_message": trace.error_message,
        "metadata": trace.metadata,
        "created_at": trace.created_at,
    }


@router.get("/executions/{execution_id}/traces", response_model=List[AgentTraceResponse])
def list_traces(
    execution_id: str,
    status: Optional[str] = Query(None, pattern=r"^(PENDING|RUNNING|COMPLETED|FAILED|SKIPPED)$"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List traces for an execution."""
    # Verify execution exists
    execution = db.query(AgentExecution).filter(
        AgentExecution.id == execution_id
    ).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    query = db.query(AgentTrace).filter(
        AgentTrace.execution_id == execution_id
    )
    
    if status:
        query = query.filter(AgentTrace.status == status)
    
    traces = query.order_by(AgentTrace.step_number.asc()).limit(limit).all()
    
    return [
        {
            "id": trace.id,
            "execution_id": trace.execution_id,
            "step_number": trace.step_number,
            "step_name": trace.step_name,
            "description": trace.description,
            "status": trace.status,
            "input_data": trace.input_data,
            "output_data": trace.output_data,
            "latency_ms": trace.latency_ms,
            "error_message": trace.error_message,
            "metadata": trace.metadata,
            "created_at": trace.created_at,
        }
        for trace in traces
    ]


@router.get("/executions/{execution_id}/traces/{trace_id}", response_model=AgentTraceResponse)
def get_trace(
    execution_id: str,
    trace_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific trace by ID."""
    trace = db.query(AgentTrace).filter(
        AgentTrace.id == trace_id,
        AgentTrace.execution_id == execution_id
    ).first()
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found"
        )
    
    return {
        "id": trace.id,
        "execution_id": trace.execution_id,
        "step_number": trace.step_number,
        "step_name": trace.step_name,
        "description": trace.description,
        "status": trace.status,
        "input_data": trace.input_data,
        "output_data": trace.output_data,
        "latency_ms": trace.latency_ms,
        "error_message": trace.error_message,
        "metadata": trace.metadata,
        "created_at": trace.created_at,
    }


@router.put("/traces/{trace_id}", response_model=AgentTraceResponse)
def update_trace(
    trace_id: str,
    payload: AgentTraceUpdate,
    db: Session = Depends(get_db),
):
    """Update a trace step."""
    trace = db.query(AgentTrace).filter(AgentTrace.id == trace_id).first()
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found"
        )
    
    if payload.status is not None:
        trace.status = payload.status
    if payload.output_data is not None:
        trace.output_data = payload.output_data
    if payload.latency_ms is not None:
        trace.latency_ms = payload.latency_ms
    if payload.error_message is not None:
        trace.error_message = payload.error_message
    if payload.metadata is not None:
        trace.metadata = payload.metadata
    
    db.commit()
    db.refresh(trace)
    
    return {
        "id": trace.id,
        "execution_id": trace.execution_id,
        "step_number": trace.step_number,
        "step_name": trace.step_name,
        "description": trace.description,
        "status": trace.status,
        "input_data": trace.input_data,
        "output_data": trace.output_data,
        "latency_ms": trace.latency_ms,
        "error_message": trace.error_message,
        "metadata": trace.metadata,
        "created_at": trace.created_at,
    }


# =============================================================================
# Execution Analytics
# =============================================================================

@router.get("/executions/stats")
def get_execution_stats(
    from_time: Optional[datetime] = Query(None),
    to_time: Optional[datetime] = Query(None),
    agent_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Get execution statistics.
    
    Returns aggregated metrics like:
    - Total executions
    - Success/failure rates
    - Average duration
    - Execution counts by status
    """
    query = db.query(AgentExecution)
    
    if from_time:
        query = query.filter(AgentExecution.created_at >= from_time)
    if to_time:
        query = query.filter(AgentExecution.created_at <= to_time)
    if agent_type:
        query = query.filter(AgentExecution.agent_type == agent_type)
    
    executions = query.all()
    
    # Calculate stats
    total = len(executions)
    by_status = {}
    total_duration = 0
    duration_count = 0
    
    for exec in executions:
        by_status[exec.status] = by_status.get(exec.status, 0) + 1
        if exec.duration_ms:
            total_duration += exec.duration_ms
            duration_count += 1
    
    avg_duration = total_duration / duration_count if duration_count > 0 else 0
    
    # Success rate (COMPLETED / total)
    success_count = by_status.get("COMPLETED", 0)
    success_rate = (success_count / total * 100) if total > 0 else 0
    
    # Failure rate
    failure_count = by_status.get("FAILED", 0)
    failure_rate = (failure_count / total * 100) if total > 0 else 0
    
    return {
        "total_executions": total,
        "by_status": by_status,
        "average_duration_ms": round(avg_duration, 2),
        "success_rate_percent": round(success_rate, 2),
        "failure_rate_percent": round(failure_rate, 2),
        "time_range": {
            "from": from_time.isoformat() if from_time else None,
            "to": to_time.isoformat() if to_time else None,
        },
        "agent_type": agent_type,
    }


@router.get("/executions/{execution_id}/summary")
def get_execution_summary(
    execution_id: str,
    db: Session = Depends(get_db),
):
    """
    Get a comprehensive summary of an execution.
    
    Includes:
    - Execution details
    - All trace steps
    - Timing information
    - Success/failure status
    """
    execution = db.query(AgentExecution).filter(
        AgentExecution.id == execution_id
    ).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    traces = db.query(AgentTrace).filter(
        AgentTrace.execution_id == execution_id
    ).order_by(AgentTrace.step_number.asc()).all()
    
    # Calculate trace statistics
    trace_stats = {
        "total_steps": len(traces),
        "completed_steps": sum(1 for t in traces if t.status == "COMPLETED"),
        "failed_steps": sum(1 for t in traces if t.status == "FAILED"),
        "skipped_steps": sum(1 for t in traces if t.status == "SKIPPED"),
        "pending_steps": sum(1 for t in traces if t.status == "PENDING"),
        "running_steps": sum(1 for t in traces if t.status == "RUNNING"),
    }
    
    # Calculate total trace duration
    total_trace_duration = sum(t.latency_ms or 0 for t in traces)
    
    # Determine overall health
    if execution.status == "COMPLETED":
        health = "HEALTHY"
    elif execution.status == "FAILED" or trace_stats["failed_steps"] > 0:
        health = "UNHEALTHY"
    elif execution.status == "RUNNING":
        health = "RUNNING"
    else:
        health = "UNKNOWN"
    
    return {
        "execution_id": execution.id,
        "trace_count": len(traces),
        "execution": {
            "id": execution.id,
            "agent_name": execution.agent_name,
            "agent_type": execution.agent_type,
            "trigger": execution.trigger,
            "status": execution.status,
            "started_at": execution.started_at,
            "completed_at": execution.completed_at,
            "duration_ms": execution.duration_ms,
            "error_message": execution.error_message,
        },
        "traces": [
            {
                "step_number": t.step_number,
                "step_name": t.step_name,
                "status": t.status,
                "latency_ms": t.latency_ms,
                "error_message": t.error_message,
            }
            for t in traces
        ],
        "trace_statistics": trace_stats,
        "total_trace_duration_ms": total_trace_duration,
        "health": health,
    }
