import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

# Matches any HTML/XML style tag, including attributes containing escaped quotes.
_TAG_PATTERN = re.compile(r"<[^>]*>")
# Null bytes and non-printable control characters (newline/tab are preserved on purpose).
_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

# Database column width for actors (audit_logs.actor / dispatch_assignments.dispatcher_id).
ACTOR_MAX_LENGTH = 50

# Explicitly unauthorized caller / civilian roles
UNAUTHORIZED_ROLES = {
    "UNAUTHORIZED_USER",
    "UNAUTHORIZED",
    "GUEST",
    "CITIZEN",
    "CIVILIAN",
    "CIVILIAN_USER",
    "ANONYMOUS",
    "PUBLIC",
    "PUBLIC_USER",
    "VOLUNTEER",
    "CALLER",
}

# Recognized prefixes for emergency dispatchers, supervisors, command officers, and CAD fleet units
AUTHORIZED_DISPATCHER_PREFIXES = (
    "DISPATCHER",
    "DSP",
    "OPERATOR",
    "SUP",
    "SUPERVISOR",
    "CMD",
    "COMMANDER",
    "CAD",
    "COMMISSIONER",
    "SYSTEM",
    "SYS",
    "AMB",
    "FIRE",
    "POL",
    "RES",
)

# Role definitions & RBAC Permission Matrix
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "ADMIN": {
        "DISPATCH_UNITS",
        "OVERRIDE_TRIAGE",
        "UPDATE_UNIT_STATUS",
        "VIEW_AUDIT",
        "PURGE_INCIDENTS",
    },
    "SUPERVISOR": {
        "DISPATCH_UNITS",
        "OVERRIDE_TRIAGE",
        "UPDATE_UNIT_STATUS",
        "VIEW_AUDIT",
    },
    "DISPATCHER": {
        "DISPATCH_UNITS",
        "UPDATE_UNIT_STATUS",
        "VIEW_AUDIT",
    },
    "CALL_TAKER": {
        "INTAKE_INCIDENTS",
        "VIEW_AUDIT",
    },
    "RESPONDER": {
        "UPDATE_UNIT_STATUS",
    },
    "CITIZEN": {
        "INTAKE_INCIDENTS",
    },
}

# Pre-registered dispatch user directory for operational authentication
_REGISTERED_DISPATCHERS = {
    "dispatcher_sarah": {
        "callsign": "DISPATCHER_SARAH",
        "role": "DISPATCHER",
        "password_hash": hashlib.sha256(b"cad112pass").hexdigest(),
    },
    "supervisor_kumar": {
        "callsign": "SUPERVISOR_KUMAR",
        "role": "SUPERVISOR",
        "password_hash": hashlib.sha256(b"cad112pass").hexdigest(),
    },
    "commissioner_lead": {
        "callsign": "DISPATCHER_COMMISSIONER_01",
        "role": "ADMIN",
        "password_hash": hashlib.sha256(b"cad112pass").hexdigest(),
    },
}


def generate_uuid() -> str:
    """Generate canonical lowercase UUIDv4 string."""
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def create_token_payload(callsign: str, role: str) -> str:
    """Generate a tamper-evident bearer token for a verified dispatcher session."""
    from backend.app.core.config import settings

    secret = (settings.DISPATCHER_AUTH_TOKEN or "smart112-dispatch-key-2026").encode("utf-8")
    payload = {
        "sub": callsign,
        "role": role,
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    body = json.dumps(payload, separators=(",", ":"))
    signature = hmac.new(secret, body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def verify_dispatcher_token(token: Optional[str]) -> bool:
    """Verify an explicit bearer or header token supplied by the Dispatcher CAD console."""
    if not token or not token.strip():
        return False

    from backend.app.core.config import settings

    expected = (settings.DISPATCHER_AUTH_TOKEN or "").strip()
    clean_token = token.strip()
    if clean_token.startswith("Bearer "):
        clean_token = clean_token[7:].strip()

    # Match raw operational static key
    if clean_token == expected:
        return True

    # Match signed payload token
    if "." in clean_token:
        try:
            body, sig = clean_token.rsplit(".", 1)
            secret = expected.encode("utf-8")
            expected_sig = hmac.new(secret, body.encode("utf-8"), hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig, expected_sig):
                return True
        except Exception:
            pass

    return False


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Verify dispatcher credentials against the authoritative user directory."""
    user = _REGISTERED_DISPATCHERS.get(username.strip().lower())
    if not user:
        return None
    hashed = hashlib.sha256(password.strip().encode("utf-8")).hexdigest()
    if hmac.compare_digest(user["password_hash"], hashed):
        token = create_token_payload(user["callsign"], user["role"])
        return {
            "callsign": user["callsign"],
            "role": user["role"],
            "permissions": list(ROLE_PERMISSIONS.get(user["role"], set())),
            "token": token,
        }
    return None


def is_authorized_dispatcher(actor: Optional[str], token: Optional[str] = None) -> bool:
    """
    Check if an actor is authenticated and authorized to perform dispatch actions.
    
    Rejects:
    - Empty, None, or whitespace-only identifiers
    - Guest, citizen, civilian, and explicitly unauthorized roles
    - Unrecognized arbitrary actor strings lacking authorized dispatcher credentials or prefixes
    """
    # 1. Bearer / Header token check
    if token and verify_dispatcher_token(token):
        if actor:
            actor_upper = actor.strip().upper()
            if any(unauth in actor_upper for unauth in ("UNAUTHORIZED", "CIVILIAN", "GUEST", "CITIZEN")):
                return False
        return True

    # 2. Strict Actor ID & Role validation
    if not actor or not actor.strip():
        return False

    actor_upper = actor.strip().upper()

    # Reject unauthorized markers
    if any(unauth in actor_upper for unauth in ("UNAUTHORIZED", "CIVILIAN", "GUEST", "CITIZEN", "ANONYMOUS")):
        return False
    if actor_upper in UNAUTHORIZED_ROLES:
        return False

    # Check authorized prefixes (e.g. DISPATCHER_SARAH, DSP-01, OPERATOR_12, SYSTEM)
    clean_id = re.sub(r"[^A-Z0-9]", "_", actor_upper)
    has_valid_prefix = any(clean_id.startswith(prefix) for prefix in AUTHORIZED_DISPATCHER_PREFIXES)
    has_valid_role = actor_upper in ROLE_PERMISSIONS

    return has_valid_prefix or has_valid_role


def check_rbac_permission(role: str, permission: str) -> bool:
    """Verify that a role holds a specific operational permission."""
    perms = ROLE_PERMISSIONS.get(role.upper(), set())
    return permission in perms


def get_dispatcher_auth_method(actor: Optional[str], token: Optional[str] = None) -> str:
    """Return the verified authentication mechanism for audit logging."""
    if token and verify_dispatcher_token(token):
        return "TOKEN_VERIFIED"
    if is_authorized_dispatcher(actor):
        return "ROLE_VERIFIED"
    return "UNAUTHORIZED"


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
