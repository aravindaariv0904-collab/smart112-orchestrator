import re
from typing import Dict, Any, List, Tuple

# Critical life-threatening emergency keywords triggering LEVEL_1_CRITICAL escalation
CRITICAL_INDICATORS = [
    "unconscious",
    "head injury",
    "severe bleeding",
    "trapped",
    "flames",
    "explosion",
    "cardiac",
    "not breathing",
    "fuel leaking",
    "overturned",
    "pinned",
    "drowning",
    "electrocution",
    "active shooter"
]

HIGH_SEVERITY_INDICATORS = [
    "fracture",
    "deep cut",
    "smoke",
    "assault",
    "robbery",
    "collision",
    "pedestrian struck"
]

def evaluate_deterministic_rules(
    raw_text: str,
    extracted_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Applies deterministic safety rules over the raw text and extracted entities.
    Enforces that high-risk signals ALWAYS escalate severity to LEVEL_1_CRITICAL,
    and missing operational parameters trigger uncertainty flags.
    """
    text_lower = (raw_text + " " + str(extracted_data)).lower()
    
    # 1. Critical Escalation Check
    escalated_severity = None
    matched_criticals = []
    for indicator in CRITICAL_INDICATORS:
        if re.search(r'\b' + re.escape(indicator) + r'\b', text_lower):
            matched_criticals.append(indicator)

    if matched_criticals or extracted_data.get("casualty_count", 0) > 1 or any(
        h in ["fire", "fuel_leak", "trapped_persons", "flames", "explosion"]
        for h in extracted_data.get("hazards", [])
    ):
        escalated_severity = "LEVEL_1_CRITICAL"
    elif any(re.search(r'\b' + re.escape(ind) + r'\b', text_lower) for ind in HIGH_SEVERITY_INDICATORS):
        escalated_severity = "LEVEL_2_HIGH"
    else:
        escalated_severity = extracted_data.get("severity", "LEVEL_3_MODERATE")

    # 2. Missing Operational Details & Uncertainty Detection
    missing_info = list(extracted_data.get("missing_information", []))
    uncertainty_detected = False
    uncertainty_flags = list(extracted_data.get("uncertainty_flags", []))

    # Check for exact location clarification
    location_markers = extracted_data.get("location_markers", [])
    if not location_markers or len(location_markers) == 0:
        if "cross street or exact landmark unknown" not in missing_info:
            missing_info.append("Exact landmark or cross-street details missing")
        uncertainty_detected = True
        uncertainty_flags.append("AMBIGUOUS_LOCATION")

    # Check for casualty count clarity
    casualty_count = extracted_data.get("casualty_count")
    if casualty_count is None or (casualty_count == 0 and "injured" in text_lower):
        if "exact casualty count unknown" not in missing_info:
            missing_info.append("Precise casualty/victim count unconfirmed")
        uncertainty_detected = True
        uncertainty_flags.append("UNCERTAIN_CASUALTIES")

    # If critical indicators are present or uncertainty detected, mandate human review
    requires_human_review = uncertainty_detected or (escalated_severity == "LEVEL_1_CRITICAL") or extracted_data.get("requires_human_review", False)

    # Consolidate results
    result = dict(extracted_data)
    result["severity"] = escalated_severity
    result["missing_information"] = list(set(missing_info))
    result["uncertainty_detected"] = uncertainty_detected
    result["uncertainty_flags"] = list(set(uncertainty_flags))
    result["requires_human_review"] = requires_human_review
    
    # Store critical trigger evidence in structured facts
    structured_facts = result.get("structured_facts", {})
    if matched_criticals:
        structured_facts["critical_triggers"] = matched_criticals
    result["structured_facts"] = structured_facts

    return result
