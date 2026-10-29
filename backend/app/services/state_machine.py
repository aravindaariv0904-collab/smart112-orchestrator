import logging
from typing import Set

logger = logging.getLogger("smart112.services.state_machine")

VALID_INCIDENT_STATUSES: Set[str] = {
    "REPORTED",
    "ASSESSED",
    "RECOMMENDED",
    "DISPATCHED",
    "ON_SCENE",
    "RESOLVED",
    "CANCELLED",
}

# Terminal states never accept further transitions.
ALLOWED_TRANSITIONS = {
    "REPORTED": {"ASSESSED", "CANCELLED"},
    "ASSESSED": {"RECOMMENDED", "DISPATCHED", "CANCELLED"},
    "RECOMMENDED": {"DISPATCHED", "CANCELLED"},
    # DISPATCHED -> RESOLVED covers administrative sign-off: field units are frequently
    # released straight from "en route" (call stood down, patient transported by a third
    # party, unit recalled). Without this edge the incident would remain DISPATCHED
    # forever while its unit is AVAILABLE, permanently blocking re-dispatch.
    "DISPATCHED": {"ON_SCENE", "RESOLVED", "CANCELLED"},
    "ON_SCENE": {"RESOLVED", "CANCELLED"},
    "RESOLVED": set(),
    "CANCELLED": set(),
}


class InvalidStateTransitionError(ValueError):
    """Raised when an incident status change violates the authoritative state machine."""


def validate_state_transition(current_status: str, target_status: str) -> bool:
    """
    Validate whether transitioning from current_status to target_status is permissible.

    Raises InvalidStateTransitionError if prohibited.
    """
    current = (current_status or "").upper()
    target = (target_status or "").upper()

    if target not in VALID_INCIDENT_STATUSES:
        raise InvalidStateTransitionError(
            f"Target status '{target}' is not a recognized state in SMART 112 state machine."
        )

    if current not in VALID_INCIDENT_STATUSES:
        raise InvalidStateTransitionError(
            f"Current status '{current}' is not a recognized state in SMART 112 state machine."
        )

    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStateTransitionError(
            f"Illegal state transition requested: '{current}' -> '{target}'. "
            f"Permitted next states from '{current}' are: {list(allowed) or 'None (Terminal state)'}."
        )

    return True
