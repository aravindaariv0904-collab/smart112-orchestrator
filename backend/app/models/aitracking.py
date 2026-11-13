"""AI agent execution tracking and notifications."""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class AgentExecution(Base):
    """Track AI agent execution with full observability."""

    __tablename__ = "agent_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_id = Column(String(50), unique=True, nullable=True, index=True, default=lambda: f"EXEC-{str(uuid4())[:8].upper()}")
    agent_name = Column(String(100), nullable=False, index=True)
    agent_version = Column(String(50), nullable=True)
    agent_type = Column(String(100), nullable=True)
    trigger = Column(String(50), default="API", nullable=True)
    
    # Parent execution for agent chains
    parent_execution_id = Column(String(36), ForeignKey("agent_executions.id"), nullable=True, index=True)
    root_execution_id = Column(String(36), ForeignKey("agent_executions.id"), nullable=True, index=True)
    
    # Input/Output
    input_data = Column(JSON, nullable=True, default=dict)
    output_data = Column(JSON, nullable=True, default=dict)
    input_summary = Column(JSON, nullable=True, default=dict)
    output_summary = Column(JSON, nullable=True, default=dict)
    tags = Column(JSON, nullable=True, default=list)
    error_data = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    execution_metadata = Column(JSON, nullable=True, default=dict)
    
    # Execution metadata
    status = Column(String(50), default="PENDING", nullable=False)
    execution_context = Column(String(50), nullable=True)
    correlation_id = Column(String(36), ForeignKey("incidents.id"), nullable=True, index=True)
    triggered_by = Column(String(50), nullable=True)
    
    # Timing
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    timeout_ms = Column(Integer, nullable=True)
    
    # Confidence tracking
    confidence_score = Column(Float, nullable=True)
    confidence_level = Column(String(50), nullable=True)
    
    # Provider tracking
    provider_name = Column(String(100), nullable=True)
    provider_model = Column(String(100), nullable=True)
    provider_latency_ms = Column(Integer, nullable=True)
    provider_cost_usd = Column(Float, nullable=True)
    
    # Call session for voice processing
    call_session_id = Column(String(36), ForeignKey("call_sessions.id"), nullable=True, index=True)
    
    # Error handling
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    last_error = Column(Text, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    parent = relationship("AgentExecution", remote_side="[AgentExecution.id]", foreign_keys="[AgentExecution.parent_execution_id]")
    root = relationship("AgentExecution", remote_side="[AgentExecution.id]", foreign_keys="[AgentExecution.root_execution_id]")
    children = relationship("AgentExecution", back_populates="parent", foreign_keys="[AgentExecution.parent_execution_id]")
    correlation = relationship("Incident", foreign_keys=[correlation_id])
    call_session = relationship("CallSession", foreign_keys=[call_session_id])
    creator = relationship("User", foreign_keys=[created_by])

    def to_dict(self, include_sensitive: bool = False) -> dict:
        data = {
            "id": self.id,
            "execution_id": self.execution_id,
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "agent_type": self.agent_type,
            "trigger": self.trigger,
            "status": self.status,
            "execution_context": self.execution_context,
            "correlation_id": self.correlation_id,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
            "provider_name": self.provider_name,
            "provider_model": self.provider_model,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "tags": self.tags or [],
            "input_summary": self.input_summary or (self.input_data if isinstance(self.input_data, dict) else {}),
            "output_summary": self.output_summary or (self.output_data if isinstance(self.output_data, dict) else {}),
            "error_message": self.error_message or self.last_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_sensitive:
            data.update({
                "input_data": self.input_data,
                "output_data": self.output_data,
                "error_data": self.error_data,
                "last_error": self.last_error,
            })
        return data

    def is_successful(self) -> bool:
        return self.status.lower() == "completed"

    def is_failed(self) -> bool:
        return self.status.lower() in ("failed", "timeout", "cancelled")


class AgentTrace(Base):
    """Step-by-step trace within an agent execution."""

    __tablename__ = "agent_traces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_id = Column(String(36), ForeignKey("agent_executions.id"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    step_name = Column(String(100), nullable=False)
    step_description = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    
    # Step I/O
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    input_data = Column(JSON, nullable=True, default=dict)
    output_data = Column(JSON, nullable=True, default=dict)
    artifacts_created = Column(String(500), default="", nullable=False)
    
    # Step metadata
    status = Column(String(50), default="COMPLETED", nullable=False)
    step_order = Column(Integer, default=1, nullable=False)
    is_critical = Column(Boolean, default=False, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    trace_metadata = Column(JSON, nullable=True, default=dict)
    
    # Timing
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    execution = relationship("AgentExecution", backref="traces")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "step_number": self.step_number,
            "step_name": self.step_name,
            "step_description": self.step_description or self.description,
            "description": self.description or self.step_description,
            "status": self.status,
            "step_order": self.step_order,
            "is_critical": self.is_critical,
            "latency_ms": self.latency_ms or self.duration_ms,
            "duration_ms": self.duration_ms or self.latency_ms,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Notification(Base):
    """In-app notification system."""

    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    notification_id = Column(String(50), unique=True, nullable=True, index=True, default=lambda: f"NOTIF-{str(uuid4())[:8].upper()}")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    recipient_id = Column(String(100), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), nullable=False)
    priority = Column(String(20), default="NORMAL", nullable=False)
    category = Column(String(100), nullable=True)
    data = Column(JSON, nullable=True, default=dict)
    channel = Column(String(50), default="IN_APP", nullable=False)
    status = Column(String(50), default="SENT", nullable=False)
    requires_ack = Column(Boolean, default=False, nullable=False)
    is_acknowledged = Column(Boolean, default=False, nullable=False)
    ack_by = Column(String(100), nullable=True)
    ack_notes = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Related entities
    related_entity_id = Column(String(100), nullable=True, index=True)
    related_entity_type = Column(String(50), nullable=True)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=True, index=True)
    assignment_id = Column(String(36), ForeignKey("dispatch_assignments.id", use_alter=True, name="fk_notification_assignment"), nullable=True, index=True)
    unit_id = Column(String(36), ForeignKey("emergency_units.id"), nullable=True, index=True)
    
    # Delivery
    delivery_channel = Column(String(50), default="in_app", nullable=False)
    delivery_status = Column(String(50), default="SENT", nullable=False)
    delivered_channels = Column(JSON, nullable=True, default=list)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    read_by = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    
    # Metadata
    notification_metadata = Column(Text, nullable=True)
    action_url = Column(String(500), nullable=True)
    action_label = Column(String(100), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_silent = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", backref="notifications", foreign_keys="[Notification.user_id]")
    incident = relationship("Incident", foreign_keys="[Notification.incident_id]")
    assignment = relationship("DispatchAssignment", foreign_keys="[Notification.assignment_id]")
    unit = relationship("EmergencyUnit", foreign_keys="[Notification.unit_id]")
    reader = relationship("User", foreign_keys=[read_by])

    def to_dict(self, include_sensitive: bool = False) -> dict:
        data = {
            "id": self.id,
            "notification_id": self.notification_id,
            "recipient_id": self.recipient_id or self.user_id,
            "title": self.title,
            "message": self.message,
            "notification_type": self.notification_type,
            "priority": self.priority,
            "category": self.category,
            "channel": self.channel or self.delivery_channel,
            "status": self.status,
            "requires_ack": self.requires_ack,
            "is_acknowledged": self.is_acknowledged,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        return data

    def mark_read(self, user_id: str) -> None:
        self.read_at = datetime.now(timezone.utc)
        self.read_by = user_id
        self.status = "READ"
        self.delivery_status = "read"
        self.updated_at = datetime.now(timezone.utc)


class NotificationTemplate(Base):
    """Reusable notification templates."""

    __tablename__ = "notification_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    template_name = Column(String(100), unique=True, nullable=True, index=True)
    name = Column(String(100), unique=True, nullable=True, index=True)
    template_type = Column(String(50), nullable=False)
    subject = Column(String(200), nullable=True)
    body = Column(Text, nullable=True)
    channels = Column(JSON, nullable=True, default=list)
    title_template = Column(String(200), default="", nullable=False)
    message_template = Column(Text, default="", nullable=False)
    priority = Column(String(20), default="NORMAL", nullable=False)
    delivery_channels = Column(String(100), default="in_app", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    variables = Column(JSON, nullable=True, default=dict)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "template_name": self.template_name or self.name,
            "name": self.name or self.template_name,
            "template_type": self.template_type,
            "subject": self.subject or self.title_template,
            "body": self.body or self.message_template,
            "title_template": self.title_template or self.subject,
            "message_template": self.message_template or self.body,
            "priority": self.priority,
            "channels": self.channels or self.get_delivery_channels(),
            "delivery_channels": self.get_delivery_channels(),
            "is_active": self.is_active,
            "description": self.description,
            "variables": self.get_variables(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def get_delivery_channels(self) -> list[str]:
        if isinstance(self.channels, list):
            return self.channels
        return [c.strip() for c in self.delivery_channels.split(",") if c.strip()]

    def get_variables(self) -> list[str]:
        if isinstance(self.variables, list):
            return self.variables
        return [v.strip() for v in self.variables.split(",") if v.strip()]

    def render(self, variables: dict) -> tuple[str, str]:
        """Render template with variables."""
        tmpl_title = self.title_template or self.subject or ""
        tmpl_body = self.message_template or self.body or ""
        title = tmpl_title.format(**variables)
        message = tmpl_body.format(**variables)
        return title, message
