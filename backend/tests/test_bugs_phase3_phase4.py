import io
import json
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit
from backend.app.models.dispatch import DispatchAssignment
from backend.app.models.audit import AuditLog
from ai.extractor import extract_emergency_facts, detect_language
from ai.rules import evaluate_deterministic_rules, check_indicator_with_negation
from multimodal.tts import synthesize_emergency_guidance
from multimodal.vision import validate_image_bytes, analyze_emergency_image


@pytest.mark.asyncio
async def test_bug_07_telugu_emergency_triage():
    # Telugu transcript: Accident near Guntur bus station, fire flames, severe bleeding
    telugu_text = "గుంటూరు బస్టాండ్ సమీపంలో ప్రమాదం జరిగింది, వాహనంలో మంటలు మరియు తీవ్ర రక్తస్రావం"
    lang = detect_language(telugu_text)
    assert lang == "te"

    facts = await extract_emergency_facts(telugu_text)
    assert facts["incident_type"] in ("TRAFFIC_ACCIDENT", "FIRE")
    assert facts["severity"] == "LEVEL_1_CRITICAL"
    assert "fire" in facts["hazards"] or "మంటలు" in str(facts.get("structured_facts", {}))


@pytest.mark.asyncio
async def test_bug_07_hindi_emergency_triage():
    # Hindi transcript: Accident with injured people and fire
    hindi_text = "सड़क पर भीषण दुर्घटना हुई है, दो लोग घायल हैं और आग लग गई है"
    lang = detect_language(hindi_text)
    assert lang == "hi"

    facts = await extract_emergency_facts(hindi_text)
    assert facts["incident_type"] in ("TRAFFIC_ACCIDENT", "FIRE")
    assert facts["severity"] == "LEVEL_1_CRITICAL"
    assert facts["casualty_count"] >= 1


def test_bug_07_multilingual_negation():
    # Telugu: "మంటలు లేవు" (no fire)
    text_te = "ప్రమాదం జరిగింది కానీ మంటలు లేవు"
    pres, neg = check_indicator_with_negation("మంటలు", text_te)
    assert pres is True
    assert neg is True


# ===========================================================================
# BUG-08: Missing TTS Integration
# ===========================================================================
def test_bug_08_tts_guidance_synthesis(client):
    response = client.post(
        "/api/v1/audio/synthesize-guidance",
        json={"guidance_type": "CPR_ASSIST", "language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["guidance_type"] == "CPR_ASSIST"
    assert "audio_base64" in data
    assert len(data["audio_base64"]) > 50
    assert data["mime_type"] in ("audio/wav", "audio/mpeg")
    assert data["duration_seconds"] > 0


def test_bug_08_tts_guidance_templates(client):
    response = client.get("/api/v1/audio/guidance-templates")
    assert response.status_code == 200
    templates = response.json().get("templates", [])
    keys = [t["type"] for t in templates]
    assert "CPR_ASSIST" in keys
    assert "FIRE_EVAC" in keys
    assert "HEMORRHAGE_CONTROL" in keys


# ===========================================================================
# BUG-09: Missing VLM Integration
# ===========================================================================
def test_bug_09_vlm_image_analysis_endpoint(client):
    # Valid minimal 1x1 PNG image
    valid_png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    files = {"file": ("crash_scene_photo.png", io.BytesIO(valid_png_bytes), "image/png")}
    response = client.post("/api/v1/vision/analyze", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["mime_type"] == "image/png"
    assert "visual_assessment" in data
    v = data["visual_assessment"]
    assert "visible_hazards" in v
    assert "damage_severity" in v
    assert data["requires_human_verification"] is True


def test_bug_09_vlm_rejects_non_image(client):
    fake_txt = io.BytesIO(b"This is not an image container")
    files = {"file": ("notes.txt", fake_txt, "text/plain")}
    response = client.post("/api/v1/vision/analyze", files=files)
    assert response.status_code == 400


# ===========================================================================
# BUG-10: Spatio-Temporal Duplicate Correlation
# ===========================================================================
def test_bug_10_spatio_temporal_duplicate_correlation(client, db_session):
    # 1. Create original incident
    resp1 = client.post(
        "/api/v1/incidents",
        json={
            "description": "Multi-car collision with fire on Ring Road",
            "latitude": 16.3050,
            "longitude": 80.4350,
        },
    )
    assert resp1.status_code == 201
    inc1 = resp1.json()

    # 2. Second report 80 meters away within 2 minutes with matching keywords
    resp2 = client.post(
        "/api/v1/incidents",
        json={
            "description": "Severe car crash near Ring Road cross with fire",
            "latitude": 16.3055,
            "longitude": 80.4355,
        },
    )
    assert resp2.status_code == 201
    inc2 = resp2.json()

    # Check duplicate flags
    assessment2 = json.loads(inc2["assessment_data"])
    assert "POTENTIAL_DUPLICATE_REPORT" in assessment2.get("uncertainty_flags", [])
    assert assessment2.get("potential_duplicate_of") == inc1["incident_number"]
    assert assessment2.get("potential_duplicate_distance_meters") < 300
    assert assessment2.get("duplicate_correlation_score") > 0.65

    # 3. Query duplicates endpoint
    dup_resp = client.get(f"/api/v1/incidents/{inc2['id']}/duplicates")
    assert dup_resp.status_code == 200
    dup_data = dup_resp.json()
    assert dup_data["total_duplicates"] >= 1
    assert any(d["candidate_id"] == inc1["id"] for d in dup_data["correlated_duplicates"])


# ===========================================================================
# BUG-11: Missing Intelligent Follow-up Questions
# ===========================================================================
def test_bug_11_intelligent_followup_questions(client):
    # Create incident with missing details
    resp = client.post(
        "/api/v1/incidents",
        json={
            "description": "Emergency here on main road, fuel leak observed, someone call help",
            "latitude": 16.3060,
            "longitude": 80.4360,
        },
    )
    assert resp.status_code == 201
    inc = resp.json()

    q_resp = client.post(f"/api/v1/incidents/{inc['id']}/follow-up-questions")
    assert q_resp.status_code == 200
    data = q_resp.json()
    assert data["total_questions"] >= 2
    questions = [q["question"].lower() for q in data["priority_questions"]]
    # Should ask about casualties and fuel risk
    assert any("injur" in q or "casualt" in q or "people" in q for q in questions)
    assert any("fuel" in q or "leak" in q for q in questions)


# ===========================================================================
# BUG-12: Live vs Simulated GPS Telemetry
# ===========================================================================
def test_bug_12_unit_simulated_telemetry(client, db_session):
    # Fetch an available unit
    unit = db_session.query(EmergencyUnit).first()
    assert unit is not None

    resp = client.get(f"/api/v1/units/{unit.id}/telemetry")
    assert resp.status_code == 200
    tel = resp.json()
    assert tel["unit_id"] == unit.id
    assert tel["is_simulated"] is True
    assert "telemetry_source" in tel
    assert "heading_degrees" in tel
    assert "speed_kmh" in tel
    assert "last_ping_utc" in tel


# ===========================================================================
# BUG-13: Incomplete Agent Orchestration
# ===========================================================================
def test_bug_13_multi_agent_workflow_orchestration(client):
    response = client.post(
        "/api/v1/orchestrator/triage-workflow",
        json={
            "transcript": "Head-on collision at market square, two victims trapped, active fuel spill",
            "latitude": 16.3067,
            "longitude": 80.4365,
            "dispatcher_callsign": "DISPATCHER_GNT_01",
        },
    )
    assert response.status_code == 200
    wf = response.json()
    assert wf["status"] == "SUCCESS"
    assert "TriageNLUAgent" in wf["coordination_agents"]
    assert "SpatialRoutingAgent" in wf["coordination_agents"]
    assert "DispatcherSupervisorAgent" in wf["coordination_agents"]
    assert wf["final_action_plan"]["decision"] in ("APPROVE_DISPATCH", "REQUIRE_OPERATOR_REVIEW", "ESCALATE_MUTUAL_AID")
    assert "primary_unit" in wf["final_action_plan"]


# ===========================================================================
# BUG-14: Real Database Analytics Verification
# ===========================================================================
def test_bug_14_live_database_analytics_dashboard(client, db_session):
    response = client.get("/api/v1/analytics/dashboard")
    assert response.status_code == 200
    dash = response.json()

    assert "incidents" in dash
    assert "fleet" in dash
    assert "performance" in dash
    assert dash["performance"]["ssot_source"] == "LIVE_DATABASE_AGGREGATE"

    # Verify counts match the actual database tables
    actual_incident_count = db_session.query(Incident).count()
    actual_unit_count = db_session.query(EmergencyUnit).count()

    assert dash["incidents"]["total"] == actual_incident_count
    assert dash["fleet"]["total_units"] == actual_unit_count
    assert isinstance(dash["performance"]["average_response_time_minutes"], (int, float))
