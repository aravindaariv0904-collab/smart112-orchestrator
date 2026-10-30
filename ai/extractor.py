import asyncio
import json
import logging
import os
import re
from typing import Any, Dict

from ai.fallback import generate_fallback_assessment
from ai.rules import check_indicator_with_negation, evaluate_deterministic_rules
from backend.app.core.config import settings

logger = logging.getLogger("smart112.ai.extractor")

SYSTEM_PROMPT = """
You are an authoritative Emergency Dispatch AI NLU Assistant for SMART 112 (State Emergency Services).
Extract structured facts from the emergency call transcript with zero hallucination.
If information is missing, ambiguous, or negated, explicitly state it in 'missing_information' or 'uncertainty_flags'.
Pay special attention to negation: 'no fire', 'not unconscious', 'no fuel leak' must NOT be marked as active hazards.

Return ONLY a JSON object with this schema:
{
  "incident_type": "TRAFFIC_ACCIDENT" | "FIRE" | "MEDICAL" | "POLICE" | "GENERAL_EMERGENCY",
  "casualty_count": integer,
  "hazards": ["fuel_leak", "fire", "trapped_persons", "smoke_inhalation", etc.],
  "location_markers": ["street", "landmark", "area"],
  "missing_information": ["exact landmark", "number of vehicles", etc.],
  "severity": "LEVEL_1_CRITICAL" | "LEVEL_2_HIGH" | "LEVEL_3_MODERATE" | "LEVEL_4_LOW",
  "confidence_score": float between 0.0 and 1.0,
  "requires_human_review": boolean
}
"""


async def _call_gemini_api(transcript: str, api_key: str) -> Dict[str, Any]:
    """Call Google Gemini API using google-genai or standard REST endpoint with JSON mode."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=[SYSTEM_PROMPT, f"EMERGENCY CALL TRANSCRIPT:\n{transcript}"],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        logger.warning(
            "Google GenAI Client error (%s), attempting fallback API call or rule-based parser.",
            e,
        )
        raise e


def _heuristic_entity_extraction(transcript: str) -> Dict[str, Any]:
    """
    High-fidelity deterministic natural language rule parser with negation handling
    and context validation for offline / zero-cost use.
    """
    text_lower = transcript.lower()

    # 1. Incident Type
    incident_type = "GENERAL_EMERGENCY"
    if any(k in text_lower for k in ["collision", "crash", "accident", "overturned", "vehicle", "car", "bus"]):
        incident_type = "TRAFFIC_ACCIDENT"
    elif any(k in text_lower for k in ["fire", "flames", "smoke", "burning"]):
        # Check if fire was negated
        _, is_neg = check_indicator_with_negation("fire", text_lower)
        if not is_neg:
            incident_type = "FIRE"
    elif any(k in text_lower for k in ["unconscious", "heart", "cardiac", "stroke", "bleeding", "patient"]):
        incident_type = "MEDICAL"
    elif any(k in text_lower for k in ["robbery", "fight", "assault", "weapon", "gun", "knife"]):
        incident_type = "POLICE"

    # 2. Hazards with Strict Negation Handling
    hazards = []
    for candidate_hazard, label in [
        ("trapped", "trapped_persons"),
        ("pinned", "trapped_persons"),
        ("fuel", "fuel_leak"),
        ("leak", "fuel_leak"),
        ("fire", "fire"),
        ("flames", "fire"),
        ("smoke", "smoke_inhalation"),
        ("explosion", "explosion"),
    ]:
        present, negated = check_indicator_with_negation(candidate_hazard, text_lower)
        if present and not negated and label not in hazards:
            hazards.append(label)

    # 3. Contextual Casualty Count (avoid confusing route numbers or vehicle counts with casualties)
    casualty_count = 0
    if any(p in text_lower for p in ["no injuries", "no casualties", "nobody hurt", "zero injuries", "everyone is safe", "no one is hurt"]):
        casualty_count = 0
    else:
        # Search for explicit casualty pattern: e.g. "2 people injured", "two victims", "one passenger trapped"
        victim_patterns = [
            r"(\b(?:one|two|three|four|five|six|\d+)\b)\s+(?:people|persons|victims|passengers|casualties)\s+(?:injured|hurt|trapped|unconscious|dead)",
            r"(?:injured|casualties|victims):\s*(\d+)",
            r"(\b(?:one|two|three|four|five|six|\d+)\b)\s+(?:are\s+)?(?:injured|hurt|trapped|unconscious)",
        ]
        word_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
        matched = False
        for pat in victim_patterns:
            m = re.search(pat, text_lower)
            if m:
                token = m.group(1).lower()
                casualty_count = word_to_num.get(token, int(token) if token.isdigit() else 0)
                matched = True
                break

        if not matched:
            # Fallback heuristic: check word proximity
            words = text_lower.split()
            for i, w in enumerate(words):
                if w in ["two", "2"] and any(
                    k in text_lower for k in ("passenger", "person", "victim", "injured", "trapped", "unconscious")
                ):
                    casualty_count = 2
                elif w in ["three", "3"] and any(k in text_lower for k in ("passenger", "person", "victim")):
                    casualty_count = 3
                elif w in ["one", "1"] and any(k in text_lower for k in ("passenger", "person", "victim")):
                    casualty_count = 1

    # 4. Location Markers
    location_markers = []
    for marker in [
        "guntur",
        "rtc",
        "bus station",
        "cross",
        "junction",
        "road",
        "circle",
        "highway",
        "station",
        "vijayawada",
        "nagar",
    ]:
        if marker in text_lower:
            location_markers.append(marker)

    # 5. Missing Information
    missing_info = []
    if not any(k in text_lower for k in ["landmark", "gate", "platform", "shop", "pillar", "near"]):
        missing_info.append("Specific landmark or pillar location needed")

    # Initial baseline severity before deterministic rules evaluate context
    present_unconscious, neg_unconscious = check_indicator_with_negation("unconscious", text_lower)
    present_trapped, neg_trapped = check_indicator_with_negation("trapped", text_lower)

    is_critical = (
        (present_unconscious and not neg_unconscious)
        or (present_trapped and not neg_trapped)
        or casualty_count > 1
        or bool(hazards)
    )

    return {
        "incident_type": incident_type,
        "casualty_count": casualty_count,
        "hazards": hazards,
        "location_markers": location_markers,
        "missing_information": missing_info,
        "severity": "LEVEL_1_CRITICAL" if is_critical else "LEVEL_2_HIGH",
        "confidence_score": 0.88,
        "structured_facts": {
            "source": "deterministic_nlp_engine",
            "extracted_markers_count": len(location_markers),
        },
    }


async def extract_emergency_facts(
    transcript: str, timeout_seconds: float = 3.0
) -> Dict[str, Any]:
    """
    Extracts structured emergency facts with a strict 3.0-second timeout guarantee.
    Enforces deterministic safety rules with negation checking and context validation.
    """
    api_key = os.getenv("GEMINI_API_KEY", getattr(settings, "GEMINI_API_KEY", ""))

    extracted = None
    try:
        if api_key and len(api_key.strip()) > 5:
            extracted = await asyncio.wait_for(
                _call_gemini_api(transcript, api_key), timeout=timeout_seconds
            )
        else:
            extracted = _heuristic_entity_extraction(transcript)
    except asyncio.TimeoutError:
        logger.warning(
            "AI Extraction exceeded %ss timeout budget. Applying fail-safe fallback.",
            timeout_seconds,
        )
        extracted = generate_fallback_assessment(transcript, "AI_CALL_TIMEOUT (>3.0s)")
    except Exception as exc:
        logger.warning(
            "AI Provider error (%s). Engaging deterministic offline fallback.", exc
        )
        extracted = _heuristic_entity_extraction(transcript)

    # Apply deterministic rules, negation checks, and context validation
    final_assessment = evaluate_deterministic_rules(transcript, extracted)
    return final_assessment
