import re
from typing import Any, Dict, List, Tuple

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
    "active shooter",
]

HIGH_SEVERITY_INDICATORS = [
    "fracture",
    "deep cut",
    "smoke",
    "assault",
    "robbery",
    "collision",
    "pedestrian struck",
]

NEGATION_PREFIXES = {
    "no",
    "not",
    "never",
    "without",
    "zero",
    "none",
    "nobody",
    "no one",
    "nothing",
    "neither",
    "nor",
    "wasn't",
    "was not",
    "isn't",
    "is not",
    "didn't",
    "did not",
    "denies",
    "denied",
    "negative",
}

NEGATION_POSTFIXES = {
    "none",
    "negative",
    "ruled out",
    "extinguished",
    "put out",
    "stopped",
    "contained",
    "cleared",
    "zero",
    "false",
}

DRILL_OR_FALSE_ALARM_TRIGGERS = [
    "drill",
    "training exercise",
    "mock drill",
    "practice call",
    "test call",
    "simulated call",
    "false alarm",
    "accidental call",
    "pocket dial",
    "stand down",
]


def check_indicator_with_negation(indicator: str, text: str) -> Tuple[bool, bool]:
    """
    Check if an indicator is present in the text, and whether it is negated.
    Returns: (is_present, is_negated)
    """
    pattern = r"\b" + re.escape(indicator) + r"\b"
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    if not matches:
        return False, False

    # If the indicator itself is "not breathing", handle specially
    if indicator == "not breathing":
        for m in matches:
            prefix_window = text[max(0, m.start() - 25) : m.start()].lower()
            if any(p in prefix_window for p in ("is breathing", "patient is", "normal")):
                return True, True
        return True, False

    negated_count = 0
    total_count = len(matches)

    for m in matches:
        start_idx = m.start()
        end_idx = m.end()

        # Look back up to 4 words (approx 35 chars) for negation prefixes
        prefix_window = text[max(0, start_idx - 35) : start_idx].lower()
        words_before = re.findall(r"\b\w+\b", prefix_window)
        has_prefix_negation = any(w in NEGATION_PREFIXES for w in words_before[-4:])

        # Look forward up to 3 words (approx 25 chars) for postfix negations
        postfix_window = text[end_idx : min(len(text), end_idx + 25)].lower()
        words_after = re.findall(r"\b\w+\b", postfix_window)
        has_postfix_negation = any(w in NEGATION_POSTFIXES for w in words_after[:3])

        if has_prefix_negation or has_postfix_negation:
            negated_count += 1

    # If every mention of the indicator is negated, it's considered negated
    is_negated = negated_count == total_count
    return True, is_negated


def evaluate_deterministic_rules(
    raw_text: str, extracted_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Applies deterministic safety rules with context validation and negation handling.
    - Accurately discounts negated keywords (e.g. 'no unconscious victims', 'no fire').
    - Detects simulated training drills, false alarms, and stand-down requests.
    - Escalates confirmed critical signals to LEVEL_1_CRITICAL conservatively.
    """
    text_lower = raw_text.lower()
    full_text = (raw_text + " " + str(extracted_data)).lower()

    # 1. Context Validation: Drills, Training Exercises & False Alarms
    is_drill_or_false_alarm = any(
        re.search(r"\b" + re.escape(trigger) + r"\b", text_lower)
        for trigger in DRILL_OR_FALSE_ALARM_TRIGGERS
    )

    # 2. Critical Indicators with Negation Handling
    affirmed_criticals: List[str] = []
    negated_criticals: List[str] = []

    for indicator in CRITICAL_INDICATORS:
        present, negated = check_indicator_with_negation(indicator, full_text)
        if present:
            if negated:
                negated_criticals.append(indicator)
            else:
                affirmed_criticals.append(indicator)

    # Check affirmed hazards
    extracted_hazards = extracted_data.get("hazards", [])
    affirmed_hazards = []
    for h in extracted_hazards:
        h_str = str(h).lower()
        # Ensure hazard wasn't negated in text
        present, negated = check_indicator_with_negation(h_str.replace("_", " "), full_text)
        if present and negated:
            continue
        affirmed_hazards.append(h)

    # Check high severity indicators with negation
    affirmed_high: List[str] = []
    for indicator in HIGH_SEVERITY_INDICATORS:
        present, negated = check_indicator_with_negation(indicator, full_text)
        if present and not negated:
            affirmed_high.append(indicator)

    # 3. Severity Resolution
    casualty_count = extracted_data.get("casualty_count", 0)

    if is_drill_or_false_alarm:
        escalated_severity = "LEVEL_4_LOW"
    elif (
        affirmed_criticals
        or casualty_count > 1
        or any(
            h in ["fire", "fuel_leak", "trapped_persons", "flames", "explosion"]
            for h in affirmed_hazards
        )
    ):
        escalated_severity = "LEVEL_1_CRITICAL"
    elif affirmed_high or casualty_count == 1:
        escalated_severity = "LEVEL_2_HIGH"
    else:
        escalated_severity = extracted_data.get("severity", "LEVEL_3_MODERATE")

    # 4. Uncertainty and Missing Operational Details
    missing_info = list(extracted_data.get("missing_information", []))
    uncertainty_detected = False
    uncertainty_flags = list(extracted_data.get("uncertainty_flags", []))

    if is_drill_or_false_alarm:
        uncertainty_detected = True
        uncertainty_flags.append("CONTEXT_DRILL_OR_FALSE_ALARM")
        missing_info.append("Caller indicated drill or false alarm - verify stand-down authorization")

    if negated_criticals:
        uncertainty_flags.append(f"NEGATED_FACTORS_{len(negated_criticals)}")

    location_markers = extracted_data.get("location_markers", [])
    if not location_markers:
        if "Exact landmark or cross-street details missing" not in missing_info:
            missing_info.append("Exact landmark or cross-street details missing")
        uncertainty_detected = True
        uncertainty_flags.append("AMBIGUOUS_LOCATION")

    # Casualty confirmation check
    if casualty_count is None or (casualty_count == 0 and "injured" in text_lower and "no injuries" not in text_lower):
        if "Precise casualty/victim count unconfirmed" not in missing_info:
            missing_info.append("Precise casualty/victim count unconfirmed")
        uncertainty_detected = True
        uncertainty_flags.append("UNCERTAIN_CASUALTIES")

    requires_human_review = (
        uncertainty_detected
        or (escalated_severity == "LEVEL_1_CRITICAL")
        or bool(extracted_data.get("requires_human_review", False))
        or is_drill_or_false_alarm
    )

    result = dict(extracted_data)
    result["severity"] = escalated_severity
    result["hazards"] = affirmed_hazards
    result["missing_information"] = list(set(missing_info))
    result["uncertainty_detected"] = uncertainty_detected
    result["uncertainty_flags"] = list(set(uncertainty_flags))
    result["requires_human_review"] = requires_human_review

    structured_facts = result.get("structured_facts", {})
    if affirmed_criticals:
        structured_facts["critical_triggers"] = affirmed_criticals
    if negated_criticals:
        structured_facts["negated_indicators"] = negated_criticals
    if is_drill_or_false_alarm:
        structured_facts["drill_or_false_alarm"] = True

    result["structured_facts"] = structured_facts
    return result
