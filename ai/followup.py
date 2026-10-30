import logging
from typing import Any, Dict, List

logger = logging.getLogger("smart112.ai.followup")


def generate_targeted_followup_questions(
    category: str,
    assessment: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Generates intelligent, life-safety-critical triage follow-up questions
    targeted directly at missing information and scene hazards (BUG-11).
    """
    category_upper = (category or "").upper()
    missing_info = [str(m).lower() for m in assessment.get("missing_information", [])]
    hazards = [str(h).lower() for h in assessment.get("hazards", [])]
    casualty_count = assessment.get("casualty_count", 0)
    flags = [str(f).lower() for f in assessment.get("uncertainty_flags", [])]

    questions = []
    prio = 1

    # 1. Casualty / Life-Safety Verification
    if casualty_count == 0 or "uncertain_casualties" in flags or any("casualty" in m for m in missing_info):
        questions.append({
            "priority": prio,
            "category": "LIFE_SAFETY",
            "question": "How many total people appear injured, unconscious, or trapped at the scene?",
            "expected_field": "casualty_count",
            "urgency": "IMMEDIATE",
        })
        prio += 1

    if any(k in category_upper for k in ("MEDICAL", "CARDIAC", "HEALTH")):
        questions.append({
            "priority": prio,
            "category": "PATIENT_STATUS",
            "question": "Is the patient conscious and breathing? Has bystander CPR been initiated?",
            "expected_field": "breathing_status",
            "urgency": "IMMEDIATE",
        })
        prio += 1

    # 2. Hazard Containment
    if any(h in hazards for h in ("fuel_leak", "fuel", "leak")):
        questions.append({
            "priority": prio,
            "category": "HAZARD_MITIGATION",
            "question": "Is fuel actively leaking near vehicle exhausts, battery cables, or ignition sources?",
            "expected_field": "fuel_ignition_risk",
            "urgency": "HIGH",
        })
        prio += 1

    if any(h in hazards for h in ("fire", "flames", "smoke_inhalation", "smoke")):
        questions.append({
            "priority": prio,
            "category": "FIRE_SUPPRESSION",
            "question": "Is the fire actively expanding or threatening nearby structures or fuel tanks?",
            "expected_field": "fire_spread_trajectory",
            "urgency": "IMMEDIATE",
        })
        prio += 1

    if any(h in hazards for h in ("trapped_persons", "pinned")):
        questions.append({
            "priority": prio,
            "category": "EXTRICATION",
            "question": "Are victims physically pinned under dashboard/steering column requiring hydraulic extrication?",
            "expected_field": "extrication_equipment_needed",
            "urgency": "HIGH",
        })
        prio += 1

    # 3. Scene Localization & Landmark Verification
    if any(k in m for m in missing_info for k in ("landmark", "cross", "location", "exact")):
        questions.append({
            "priority": prio,
            "category": "LOCALIZATION",
            "question": "What is the closest visible mile-marker, shop name, signal pole, or pillar number?",
            "expected_field": "exact_landmark_reference",
            "urgency": "HIGH",
        })
        prio += 1

    # 4. Caller Contact Safety Net
    questions.append({
        "priority": prio,
        "category": "CALLER_LINE",
        "question": "What is your call-back phone number and your exact current physical vantage point?",
        "expected_field": "caller_callback_contact",
        "urgency": "STANDARD",
    })

    return questions
