import logging
from typing import Dict, Any

logger = logging.getLogger("smart112.ai.fallback")

def generate_fallback_assessment(raw_text: str, reason: str = "Timeout or API Failure") -> Dict[str, Any]:
    """
    Instantaneous deterministic fallback assessment when AI model execution
    encounters timeout (>3.0s), network failure, quota depletion, or malformed schema.
    Guarantees that emergency dispatch processing never blocks.
    """
    logger.warning(f"Generating fail-safe fallback assessment. Reason: {reason}")
    
    return {
        "status": "fallback_applied",
        "incident_type": "UNCLASSIFIED",
        "severity": "LEVEL_2_HIGH",
        "casualty_count": 0,
        "hazards": ["POTENTIAL_HAZARDS_UNASSESSED"],
        "location_markers": [],
        "missing_information": ["AI Extraction Failed - Human Verification Required"],
        "uncertainty_detected": True,
        "uncertainty_flags": ["AI_TIMEOUT_OR_ERROR", reason[:50]],
        "requires_human_review": True,
        "confidence_score": 0.0,
        "structured_facts": {
            "fallback_reason": reason,
            "raw_text_preserved": raw_text[:200]
        }
    }
