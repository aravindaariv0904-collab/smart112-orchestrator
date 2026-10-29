from ai.rules import evaluate_deterministic_rules

def test_critical_keyword_escalation():
    raw_text = "Two vehicles collided. One victim is unconscious and trapped inside the driver seat."
    extracted = {
        "incident_type": "TRAFFIC_ACCIDENT",
        "casualty_count": 1,
        "hazards": ["trapped_persons"],
        "location_markers": ["highway"],
        "missing_information": [],
        "severity": "LEVEL_3_MODERATE"
    }

    result = evaluate_deterministic_rules(raw_text, extracted)
    
    # Must escalate to LEVEL_1_CRITICAL due to 'unconscious' and 'trapped'
    assert result["severity"] == "LEVEL_1_CRITICAL"
    assert result["requires_human_review"] is True
    assert "critical_triggers" in result["structured_facts"]

def test_fuel_leak_hazard_escalation():
    raw_text = "Minor collision but fuel leaking rapidly across the asphalt near a generator."
    extracted = {
        "incident_type": "TRAFFIC_ACCIDENT",
        "casualty_count": 0,
        "hazards": ["fuel_leak"],
        "location_markers": [],
        "missing_information": [],
        "severity": "LEVEL_4_LOW"
    }

    result = evaluate_deterministic_rules(raw_text, extracted)
    assert result["severity"] == "LEVEL_1_CRITICAL"
    assert result["uncertainty_detected"] is True

def test_missing_location_flags_uncertainty():
    raw_text = "Somebody broke a window here, send someone."
    extracted = {
        "incident_type": "POLICE",
        "casualty_count": 0,
        "hazards": [],
        "location_markers": [],
        "missing_information": [],
        "severity": "LEVEL_3_MODERATE"
    }

    result = evaluate_deterministic_rules(raw_text, extracted)
    assert result["uncertainty_detected"] is True
    assert "AMBIGUOUS_LOCATION" in result["uncertainty_flags"]
    assert any("landmark" in m.lower() for m in result["missing_information"])
