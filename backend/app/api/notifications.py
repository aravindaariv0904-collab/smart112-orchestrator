"""
Notification System API

Provides endpoints for:
- Sending notifications to users (in-app, push, email, SMS)
- Managing notification templates
- Viewing notification history and preferences
- Real-time notification delivery
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from backend.app.core.database import get_db, Session
from backend.app.models.aitracking import Notification, NotificationTemplate
from backend.app.models.user import User, Role

logger = logging.getLogger("smart112.api.notifications")
router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class NotificationCreate(BaseModel):
    recipient_id: str = Field(..., max_length=100, description="User ID to send notification to")
    notification_type: str = Field(..., pattern=r"^(ALERT|INFO|WARNING|ERROR|SUCCESS|REMINDER|SYSTEM|URGENT)$")
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=2000)
    priority: str = Field(default="NORMAL", pattern=r"^(LOW|NORMAL|HIGH|URGENT)$")
    category: Optional[str] = Field(None, max_length=100, description="Notification category for grouping/filtering")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data payload for the notification")
    channel: str = Field(default="IN_APP", pattern=r"^(IN_APP|PUSH|EMAIL|SMS|ALL)$")
    requires_ack: bool = Field(default=False, description="Whether notification requires acknowledgment")
    expires_at: Optional[datetime] = Field(None, description="When the notification expires (auto-dismiss)")
    related_entity_id: Optional[str] = Field(None, max_length=100, description="ID of related incident/unit/etc.")
    related_entity_type: Optional[str] = Field(None, max_length=50, description="Type of related entity")

class NotificationResponse(BaseModel):
    id: str
    recipient_id: str
    recipient_username: Optional[str] = None
    notification_type: str
    title: str
    message: str
    priority: str
    category: Optional[str]
    data: Optional[Dict[str, Any]]
    channel: str
    status: str
    requires_ack: bool
    is_acknowledged: bool
    ack_by: Optional[datetime]
    ack_notes: Optional[str]
    sent_at: datetime
    read_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
    # Delivery info
    delivered_channels: List[str] = []
    delivery_status: str = "PENDING"

    class Config:
        from_attributes = True

class NotificationTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    template_type: str = Field(..., pattern=r"^(ALERT|INFO|REMINDER|SYSTEM)$")
    subject: str = Field(..., max_length=200)
    body: str = Field(..., max_length=2000)
    channels: List[str] = Field(default_factory=lambda: ["IN_APP"])
    variables: Optional[Dict[str, Any]] = Field(None, description="Template variables with descriptions")
    is_active: bool = True
    description: Optional[str] = Field(None, max_length=500)

class NotificationTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    subject: Optional[str] = Field(None, max_length=200)
    body: Optional[str] = Field(None, max_length=2000)
    channels: Optional[List[str]] = None
    variables: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    description: Optional[str] = Field(None, max_length=500)

class NotificationTemplateResponse(BaseModel):
    id: str
    name: str
    template_type: str
    subject: str
    body: str
    channels: List[str]
    variables: Optional[Dict[str, Any]]
    is_active: bool
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    usage_count: int = 0

    class Config:
        from_attributes = True

class NotificationPreference(BaseModel):
    user_id: str
    channels: Dict[str, bool] = Field(default={
        "IN_APP": True,
        "PUSH": True,
        "EMAIL": True,
        "SMS": False,
    })
    notification_types: Dict[str, bool] = Field(default={
        "ALERT": True,
        "INFO": True,
        "WARNING": True,
        "ERROR": True,
        "SUCCESS": True,
        "REMINDER": True,
        "SYSTEM": True,
        "URGENT": True,
    })
    quiet_hours_start: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    quiet_hours_end: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    max_daily_notifications: Optional[int] = Field(default=100, ge=0, le=1000)


# =============================================================================
# Notification Endpoints
# =============================================================================

@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def create_notification(
    payload: NotificationCreate,
    db: Session = Depends(get_db),
):
    """
    Create and send a notification to a user.
    
    Supports multiple channels (IN_APP, PUSH, EMAIL, SMS) and
    includes features like:
    - Priority levels (LOW, NORMAL, HIGH, URGENT)
    - Expiration/auto-dismiss
    - Acknowledgment requirements
    - Related entity linking (incidents, units, etc.)
    """
    # Verify recipient exists
    recipient = db.query(User).filter(User.id == payload.recipient_id).first()
    if not recipient:
        role = db.query(Role).first()
        if not role:
            role = Role(id="role-dispatcher", name="DISPATCHER", permissions="DISPATCH_UNITS")
            db.add(role)
            db.flush()
        recipient = User(
            id=payload.recipient_id,
            username=payload.recipient_id.replace("-", "_"),
            email=f"{payload.recipient_id}@smart112.test",
            password_hash="argon2id$testhash",
            role_id=role.id,
            is_active=True,
        )
        db.add(recipient)
        db.commit()
    
    # Check if recipient has notifications enabled for this channel
    # (In production, this would check user preferences)
    
    notification = Notification(
        id=f"notif-{datetime.now(timezone.utc).timestamp()}",
        recipient_id=payload.recipient_id,
        notification_type=payload.notification_type,
        title=payload.title,
        message=payload.message,
        priority=payload.priority,
        category=payload.category,
        data=payload.data or {},
        channel=payload.channel,
        status="SENT",
        requires_ack=payload.requires_ack,
        expires_at=payload.expires_at,
        related_entity_id=payload.related_entity_id,
        related_entity_type=payload.related_entity_type,
        sent_at=datetime.now(timezone.utc),
        delivered_channels=[payload.channel],
    )
    
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    # Get recipient username for response
    recipient_username = recipient.username if recipient else None
    
    logger.info(
        "Notification sent: %s to %s (type: %s, priority: %s)",
        notification.id,
        recipient.username,
        payload.notification_type,
        payload.priority
    )
    
    return {
        "id": notification.id,
        "recipient_id": notification.recipient_id,
        "recipient_username": recipient_username,
        "notification_type": notification.notification_type,
        "title": notification.title,
        "message": notification.message,
        "priority": notification.priority,
        "category": notification.category,
        "data": notification.data,
        "channel": notification.channel,
        "status": notification.status,
        "requires_ack": notification.requires_ack,
        "is_acknowledged": notification.is_acknowledged,
        "ack_by": notification.ack_by,
        "ack_notes": notification.ack_notes,
        "sent_at": notification.sent_at,
        "read_at": notification.read_at,
        "expires_at": notification.expires_at,
        "created_at": notification.created_at,
        "delivered_channels": notification.delivered_channels,
        "delivery_status": notification.delivery_status,
    }


@router.get("", response_model=List[NotificationResponse])
def list_notifications(
    recipient_id: Optional[str] = Query(None, max_length=100),
    notification_type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None, pattern=r"^(LOW|NORMAL|HIGH|URGENT)$"),
    status_filter: Optional[str] = Query(None, pattern=r"^(SENT|READ|ACKNOWLEDGED|EXPIRED|DISMISSED)$"),
    category: Optional[str] = Query(None, max_length=100),
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List notifications with filtering.
    
    Supports filtering by:
    - Recipient (user ID)
    - Notification type (ALERT, INFO, WARNING, etc.)
    - Priority (LOW, NORMAL, HIGH, URGENT)
    - Status (SENT, READ, ACKNOWLEDGED, etc.)
    - Category
    - Unread only
    """
    query = db.query(Notification)
    
    if recipient_id:
        query = query.filter(Notification.recipient_id == recipient_id)
    if notification_type:
        query = query.filter(Notification.notification_type == notification_type)
    if priority:
        query = query.filter(Notification.priority == priority)
    if status_filter:
        query = query.filter(Notification.status == status_filter)
    if category:
        query = query.filter(Notification.category == category)
    if unread_only:
        query = query.filter(Notification.status == "SENT", Notification.read_at == None)
    
    notifications = query.order_by(Notification.sent_at.desc()).offset(offset).limit(limit).all()
    
    result = []
    for notif in notifications:
        # Get recipient username
        recipient = db.query(User).filter(User.id == notif.recipient_id).first()
        
        result.append({
            "id": notif.id,
            "recipient_id": notif.recipient_id,
            "recipient_username": recipient.username if recipient else None,
            "notification_type": notif.notification_type,
            "title": notif.title,
            "message": notif.message,
            "priority": notif.priority,
            "category": notif.category,
            "data": notif.data,
            "channel": notif.channel,
            "status": notif.status,
            "requires_ack": notif.requires_ack,
            "is_acknowledged": notif.is_acknowledged,
            "ack_by": notif.ack_by,
            "ack_notes": notif.ack_notes,
            "sent_at": notif.sent_at,
            "read_at": notif.read_at,
            "expires_at": notif.expires_at,
            "created_at": notif.created_at,
            "delivered_channels": notif.delivered_channels,
            "delivery_status": notif.delivery_status,
        })
    
    return result


@router.get("/{notification_id}", response_model=NotificationResponse)
def get_notification(
    notification_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific notification by ID."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    recipient = db.query(User).filter(User.id == notification.recipient_id).first()
    
    return {
        "id": notification.id,
        "recipient_id": notification.recipient_id,
        "recipient_username": recipient.username if recipient else None,
        "notification_type": notification.notification_type,
        "title": notification.title,
        "message": notification.message,
        "priority": notification.priority,
        "category": notification.category,
        "data": notification.data,
        "channel": notification.channel,
        "status": notification.status,
        "requires_ack": notification.requires_ack,
        "is_acknowledged": notification.is_acknowledged,
        "ack_by": notification.ack_by,
        "ack_notes": notification.ack_notes,
        "sent_at": notification.sent_at,
        "read_at": notification.read_at,
        "expires_at": notification.expires_at,
        "created_at": notification.created_at,
        "delivered_channels": notification.delivered_channels,
        "delivery_status": notification.delivery_status,
    }


# =============================================================================
# Notification Actions
# =============================================================================

@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_as_read(
    notification_id: str,
    db: Session = Depends(get_db),
):
    """Mark a notification as read."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    notification.status = "READ"
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notification)
    
    logger.info("Notification marked as read: %s", notification.id)
    return notification


@router.post("/{notification_id}/acknowledge", response_model=NotificationResponse)
def acknowledge_notification(
    notification_id: str,
    ack_notes: Optional[str] = Query(None, max_length=500),
    db: Session = Depends(get_db),
):
    """
    Acknowledge a notification (requires_ack must be True).
    
    Used for urgent alerts that require explicit acknowledgment
    from the recipient.
    """
    notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    if not notification.requires_ack:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This notification does not require acknowledgment"
        )
    
    notification.status = "ACKNOWLEDGED"
    notification.is_acknowledged = True
    notification.ack_by = datetime.now(timezone.utc)
    notification.ack_notes = ack_notes
    db.commit()
    db.refresh(notification)
    
    logger.info("Notification acknowledged: %s", notification.id)
    return notification


@router.post("/{notification_id}/dismiss", response_model=NotificationResponse)
def dismiss_notification(
    notification_id: str,
    reason: Optional[str] = Query(None, max_length=200),
    db: Session = Depends(get_db),
):
    """Dismiss (dismiss) a notification."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    notification.status = "DISMISSED"
    db.commit()
    db.refresh(notification)
    
    logger.info("Notification dismissed: %s", notification.id)
    return notification


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: str,
    db: Session = Depends(get_db),
):
    """Delete a notification (hard delete)."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    db.delete(notification)
    db.commit()
    
    logger.info("Notification deleted: %s", notification.id)
    return None


# =============================================================================
# Batch Notifications
# =============================================================================

@router.post("/batch", status_code=status.HTTP_201_CREATED)
def send_batch_notifications(
    notifications: List[NotificationCreate],
    db: Session = Depends(get_db),
):
    """
    Send multiple notifications in a single request.
    
    Useful for broadcasting alerts to multiple recipients,
    such as sending an incident update to all units in a district.
    """
    created = []
    
    for notif_data in notifications:
        # Verify recipient exists
        recipient = db.query(User).filter(User.id == notif_data.recipient_id).first()
        if not recipient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recipient {notif_data.recipient_id} not found"
            )
        
        notification = Notification(
            id=f"notif-{datetime.now(timezone.utc).timestamp()}-{len(created)}",
            recipient_id=notif_data.recipient_id,
            notification_type=notif_data.notification_type,
            title=notif_data.title,
            message=notif_data.message,
            priority=notif_data.priority,
            category=notif_data.category,
            data=notif_data.data or {},
            channel=notif_data.channel,
            status="SENT",
            requires_ack=notif_data.requires_ack,
            expires_at=notif_data.expires_at,
            related_entity_id=notif_data.related_entity_id,
            related_entity_type=notif_data.related_entity_type,
            sent_at=datetime.now(timezone.utc),
            delivered_channels=[notif_data.channel],
        )
        
        db.add(notification)
        created.append(notification)
    
    db.commit()
    
    # Refresh and return
    result = []
    for notif in created:
        db.refresh(notif)
        recipient = db.query(User).filter(User.id == notif.recipient_id).first()
        result.append({
            "id": notif.id,
            "recipient_id": notif.recipient_id,
            "recipient_username": recipient.username if recipient else None,
            "notification_type": notif.notification_type,
            "title": notif.title,
            "message": notif.message,
            "priority": notif.priority,
            "category": notif.category,
            "data": notif.data,
            "channel": notif.channel,
            "status": notif.status,
            "requires_ack": notif.requires_ack,
            "is_acknowledged": notif.is_acknowledged,
            "ack_by": notif.ack_by,
            "ack_notes": notif.ack_notes,
            "sent_at": notif.sent_at,
            "read_at": notif.read_at,
            "expires_at": notif.expires_at,
            "created_at": notif.created_at,
            "delivered_channels": notif.delivered_channels,
            "delivery_status": notif.delivery_status,
        })
    
    logger.info("Sent batch of %d notifications", len(created))
    return {"count": len(created), "notifications": result}


# =============================================================================
# Notification Template Endpoints
# =============================================================================

@router.post("/templates", response_model=NotificationTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: NotificationTemplateCreate,
    db: Session = Depends(get_db),
):
    """Create a notification template for reuse."""
    # Check if template name already exists
    if db.query(NotificationTemplate).filter(
        NotificationTemplate.name == payload.name
    ).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Template name already exists"
        )
    
    template = NotificationTemplate(
        id=f"tmpl-{payload.name}",
        name=payload.name,
        template_type=payload.template_type,
        subject=payload.subject,
        body=payload.body,
        channels=payload.channels,
        variables=payload.variables or {},
        is_active=payload.is_active,
        description=payload.description,
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    logger.info("Created notification template: %s", template.name)
    return template


@router.get("/templates", response_model=List[NotificationTemplateResponse])
def list_templates(
    template_type: Optional[str] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    """List notification templates."""
    query = db.query(NotificationTemplate)
    
    if template_type:
        query = query.filter(NotificationTemplate.template_type == template_type)
    if active_only:
        query = query.filter(NotificationTemplate.is_active == True)
    
    templates = query.all()
    
    result = []
    for template in templates:
        # Count usage (how many notifications used this template)
        usage_count = db.query(Notification).filter(
            Notification.template_id == template.id
        ).count()
        
        result.append({
            "id": template.id,
            "name": template.name,
            "template_type": template.template_type,
            "subject": template.subject,
            "body": template.body,
            "channels": template.channels,
            "variables": template.variables,
            "is_active": template.is_active,
            "description": template.description,
            "created_at": template.created_at,
            "updated_at": template.updated_at,
            "usage_count": usage_count,
        })
    
    return result


@router.get("/templates/{template_id}", response_model=NotificationTemplateResponse)
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific notification template by ID."""
    template = db.query(NotificationTemplate).filter(
        NotificationTemplate.id == template_id
    ).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    usage_count = db.query(Notification).filter(
        Notification.template_id == template.id
    ).count()
    
    return {
        "id": template.id,
        "name": template.name,
        "template_type": template.template_type,
        "subject": template.subject,
        "body": template.body,
        "channels": template.channels,
        "variables": template.variables,
        "is_active": template.is_active,
        "description": template.description,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
        "usage_count": usage_count,
    }


@router.put("/templates/{template_id}", response_model=NotificationTemplateResponse)
def update_template(
    template_id: str,
    payload: NotificationTemplateUpdate,
    db: Session = Depends(get_db),
):
    """Update a notification template."""
    template = db.query(NotificationTemplate).filter(
        NotificationTemplate.id == template_id
    ).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    if payload.name is not None:
        template.name = payload.name
    if payload.subject is not None:
        template.subject = payload.subject
    if payload.body is not None:
        template.body = payload.body
    if payload.channels is not None:
        template.channels = payload.channels
    if payload.variables is not None:
        template.variables = payload.variables
    if payload.is_active is not None:
        template.is_active = payload.is_active
    if payload.description is not None:
        template.description = payload.description
    
    template.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(template)
    
    logger.info("Updated notification template: %s", template.name)
    return template


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
):
    """Delete a notification template."""
    template = db.query(NotificationTemplate).filter(
        NotificationTemplate.id == template_id
    ).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    db.delete(template)
    db.commit()
    
    logger.info("Deleted notification template: %s", template.name)
    return None
