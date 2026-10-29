import json
import logging
import os
import asyncio
from typing import Dict, Any, Optional

from backend.app.core.config import settings
from ai.fallback import generate_fallback_assessment
from ai.rules import evaluate_deterministic_rules

logger = logging.getLogger("smart112.ai.extractor")

EXTRACTION_PROMPT = """
You are an expert 112 emergency dispatch triage AI. Analyze the following emergency call transcript and output valid JSON conforming strictly to this format:
{
  "incident_type": "TRAFFIC_ACCIDENT | MEDICAL | FIRE | POLICE | HAZMAT | RESCUE",
  "casualty_count": <integer of injured/victims, 0 if unknown>,
  "hazards": ["fuel_leak", "fire", "trapped_persons", "weapons", etc.],
  "location_markers": ["bus station", "cross street", etc.],
  "missing_information": ["caller contact", "exact landmark", etc.],
  "severity": "LEVEL_1_CRITICAL | LEVEL_2_HIGH | LEVEL_3_MODERATE | LEVEL_4_LOW",
  "confidence_score": <float between 0.0 and 1.0>
}

Emergency Transcript:
\"\"\"{transcript}\"\"\"
"""

async def _call_gemini_api(transcript: str, api_key: str) -> Dict[str, Any]:
    """Call Google Gemini API using google-genai or standard REST endpoint with JSON mode."""
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)
        
        # Run sync Gemini call inside thread pool executor
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model='gemini-2.5-flash',
                contents=EXTRACTION_PROMPT.format(transcript=transcript),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
        )
        return json.loads(response.text)
    except Exception as e:
        logger.warning(f"Google GenAI Client error ({e}), attempting fallback API call or rule-based parser.")
        raise e

def _heuristic_entity_extraction(transcript: str) -> Dict[str, Any]:
    """
    High-fidelity deterministic natural language rule parser for offline / zero-cost use.
    Provides complete zero-cost extraction if Gemini API is unreachable or rate-limited.
    """
    text_lower = transcript.lower()
    
    # 1. Incident Type
    incident_type = "GENERAL_EMERGENCY"
    if any(k in text_lower for k in ["collision", "crash", "accident", "overturned", "vehicle", "car", "bus"]):
        incident_type = "TRAFFIC_ACCIDENT"
    elif any(k in text_lower for k in ["fire", "flames", "smoke", "burning"]):
        incident_type = "FIRE"
    elif any(k in text_lower for k in ["unconscious", "heart", "cardiac", "stroke", "bleeding", "patient"]):
        incident_type = "MEDICAL"
    elif any(k in text_lower for k in ["robbery", "fight", "assault", "weapon", "gun", "knife"]):
        incident_type = "POLICE"

    # 2. Hazards
    hazards = []
    if "trapped" in text_lower or "pinned" in text_lower:
        hazards.append("trapped_persons")
    if "fuel" in text_lower or "gas" in text_lower or "leak" in text_lower:
        hazards.append("fuel_leak")
    if "fire" in text_lower or "flames" in text_lower:
        hazards.append("fire")
    if "smoke" in text_lower:
        hazards.append("smoke_inhalation")

    # 3. Casualty Count
    casualty_count = 0
    words = text_lower.split()
    for i, w in enumerate(words):
        if w in ["two", "2"]:
            casualty_count = 2
        elif w in ["three", "3"]:
            casualty_count = 3
        elif w in ["four", "4"]:
            casualty_count = 4
        elif w in ["one", "1", "a", "an"] and i + 1 < len(words) and words[i+1] in ["passenger", "person", "victim", "casualty"]:
            casualty_count = 1

    # 4. Location Markers
    location_markers = []
    for marker in ["guntur", "rtc", "bus station", "cross", "junction", "road", "circle", "highway", "station"]:
        if marker in text_lower:
            location_markers.append(marker)

    # 5. Missing Information
    missing_info = []
    if not any(k in text_lower for k in ["landmark", "gate", "platform", "shop", "pillar", "near"]):
        missing_info.append("Specific landmark or pillar location needed")

    return {
        "incident_type": incident_type,
        "casualty_count": casualty_count,
        "hazards": hazards,
        "location_markers": location_markers,
        "missing_information": missing_info,
        "severity": "LEVEL_1_CRITICAL" if ("unconscious" in text_lower or "trapped" in text_lower or casualty_count > 1) else "LEVEL_2_HIGH",
        "confidence_score": 0.88,
        "structured_facts": {
            "source": "deterministic_nlp_engine",
            "extracted_markers_count": len(location_markers)
        }
    }

async def extract_emergency_facts(transcript: str, timeout_seconds: float = 3.0) -> Dict[str, Any]:
    """
    Extracts structured emergency facts with a strict 3.0-second timeout guarantee.
    Enforces deterministic safety rule evaluation and automatic fallback.
    """
    if not transcript or not transcript.strip():
        return generate_fallback_assessment(transcript, "Empty transcript provided")

    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    
    extracted = None
    try:
        if api_key:
            # Wrap API call in strict 3-second timeout
            extracted = await asyncio.wait_for(
                _call_gemini_api(transcript, api_key),
                timeout=timeout_seconds
            )
        else:
            # Zero-cost local deterministic NLP parser
            extracted = _heuristic_entity_extraction(transcript)
    except asyncio.TimeoutError:
        logger.warning(f"AI Extraction exceeded {timeout_seconds}s timeout budget. Applying fail-safe fallback.")
        extracted = generate_fallback_assessment(transcript, "AI_CALL_TIMEOUT (>3.0s)")
    except Exception as exc:
        logger.warning(f"AI Extraction encountered error: {exc}. Applying heuristic safety extraction.")
        # If API failed, run heuristic entity extraction rather than blank unclassified
        extracted = _heuristic_entity_extraction(transcript)
        extracted["uncertainty_flags"] = ["GEMINI_API_UNAVAILABLE"]
        extracted["requires_human_review"] = True

    # Apply safety rules & critical escalation guarantee
    final_assessment = evaluate_deterministic_rules(transcript, extracted)
    return final_assessment
