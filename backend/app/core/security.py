import re
import uuid
from datetime import datetime, timezone
from typing import Optional

# Matches any HTML/XML style tag, including attributes containing escaped quotes.
_TAG_PATTERN = re.compile(r"<[^>]*>")
# Null bytes and non-printable control characters (newline/tab are preserved on purpose).
_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


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
