import re
import uuid
from datetime import datetime, timezone
from typing import Optional

# Matches any HTML/XML style tag, including attributes containing escaped quotes.
_TAG_PATTERN = re.compile(r"<[^>]*>")
# Null bytes and non-printable control characters (newline/tab are preserved on purpose).
_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

# Database column width for actors (audit_logs.actor / dispatch_assignments.dispatcher_id).
ACTOR_MAX_LENGTH = 50

UNAUTHORIZED_ROLES = {"UNAUTHORIZED_USER", "GUEST", "CITIZEN", "CIVILIAN", "ANONYMOUS"}


def generate_uuid() -> str:
    """Generate canonical lowercase UUIDv4 string."""
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def is_authorized_dispatcher(actor: Optional[str]) -> bool:
    """
    Check if an actor is authorized to perform dispatch actions.
    Rejects guest/citizen/unauthorized identifiers.
    """
    if not actor or not actor.strip():
        return False
    actor_upper = actor.strip().upper()
    if "UNAUTHORIZED" in actor_upper:
        return False
    if actor_upper in UNAUTHORIZED_ROLES:
        return False
    return True


def sanitize_actor_id(actor: Optional[str]) -> str:
    """
    Sanitise a dispatcher/system identifier.

    Truncates to the 50 character column width so an oversized client-supplied
    identifier can never trigger a database length error mid-transaction.
    """
    if not actor or not actor.strip():
        return "DISPATCHER_UNKNOWN"
    return actor.strip().upper()[:ACTOR_MAX_LENGTH]


def sanitize_text(value: Optional[str], max_length: int = 5000) -> Optional[str]:
    """
    Strip markup and control characters from free-text input.

    Tags are removed first, then any orphaned angle brackets are dropped so that a
    fragmented payload (e.g. `<scr<script>ipt>`) cannot be reassembled into markup.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)

    cleaned = _TAG_PATTERN.sub("", value)
    cleaned = _CONTROL_PATTERN.sub("", cleaned)
    cleaned = cleaned.replace("<", "").replace(">", "")
    return cleaned.strip()[:max_length]
