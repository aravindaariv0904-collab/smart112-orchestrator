import pytest
from ai.fallback import generate_fallback_assessment
from ai.extractor import extract_emergency_facts

def test_generate_fallback_assessment_structure():
    raw_text = "Urgent help needed at market circle, caller hung up."
    fallback = generate_fallback_assessment(raw_text, "Test Timeout Simulation")

    assert fallback["status"] == "fallback_applied"
    assert fallback["incident_type"] == "UNCLASSIFIED"
    assert fallback["severity"] == "LEVEL_2_HIGH"
    assert fallback["requires_human_review"] is True
    assert "AI Extraction Failed - Human Verification Required" in fallback["missing_information"]
    assert "AI_TIMEOUT_OR_ERROR" in fallback["uncertainty_flags"]

@pytest.mark.asyncio
async def test_extract_emergency_facts_with_empty_or_failing_key():
    # Empty transcript
    empty_result = await extract_emergency_facts("")
    assert empty_result["requires_human_review"] is True

    # Real emergency text under zero-cost / fallback mode
    text = "Bus overturned near Guntur bypass, people trapped and crying for help."
    result = await extract_emergency_facts(text, timeout_seconds=1.0)
    
    assert "severity" in result
    assert result["severity"] in ["LEVEL_1_CRITICAL", "LEVEL_2_HIGH"]
    assert "casualty_count" in result
    assert "hazards" in result
