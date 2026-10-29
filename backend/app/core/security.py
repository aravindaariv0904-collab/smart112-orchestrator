from datetime import datetime, timezone
import uuid

def generate_uuid() -> str:
    """Generate canonical lowercase UUIDv4 string."""
    return str(uuid.uuid4())

def get_utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

def sanitize_actor_id(actor: str) -> str:
    """Sanitize dispatcher/system identifier."""
    if not actor or not actor.strip():
        return "DISPATCHER_UNKNOWN"
    return actor.strip().upper()
