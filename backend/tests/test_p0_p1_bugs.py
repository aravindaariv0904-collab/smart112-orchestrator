import io
import json
from datetime import datetime, timezone

import pytest

from ai.extractor import extract_emergency_facts
from ai.rules import check_indicator_with_negation, evaluate_deterministic_rules
from backend.app.core.security import is_authorized_dispatcher
from backend.app.models.audit import AuditLog
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit
from backend.app.services.matcher import is_unit_eligible, match_candidate_units


# ===========================================================================
# BUG-01: Weak Dispatcher Authentication & Backend-Enforced RBAC
# ===========================================================================
def test_bug_01_dispatcher_login_and_token_exchange(client):
    # 1. Valid dispatcher credentials -> 200 OK
    resp_valid = client.post(
        "/api/v1/auth/login",
        json={"username": "dispatcher_sarah", "password": "cad112pass"},
    )
    assert resp_valid.status_code == 200
    data = resp_valid.json()
    assert data["role"] == "DISPATCHER"
    assert data["callsign"] == "DISPATCHER_SARAH"
    assert "DISPATCH_UNITS" in data["permissions"]
    token = data["access_token"]
    assert len(token) > 20

    # 2. Invalid dispatcher credentials -> 401 Unauthorized
    resp_invalid = client.post(
        "/api/v1/auth/login",
        json={"username": "dispatcher_sarah", "password": "wrongpassword"},
    )
    assert resp_invalid.status_code == 401

    # 3. Verify session token endpoint
    resp_verify = client.get(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_verify.status_code == 200
    assert resp_verify.json()["valid"] is True


def test_bug_01_rbac_rejection_for_unauthorized_actors(client, db_session):
    incident = Incident(
        id="inc-rbac-test-01",
        incident_number="INC-2026-RBAC01",
        description="Testing RBAC enforcement",
        category="TRAFFIC_ACCIDENT",
        status="RECOMMENDED",
        severity="LEVEL_2_HIGH",
        latitude=16.3067,
        longitude=80.4365,
        requires_human_review=False,
    )
    unit = db_session.query(EmergencyUnit).filter(EmergencyUnit.status == "AVAILABLE").first()
    db_session.add(incident)
    db_session.commit()

    # Unauthorized role rejected with 403
    resp_unauth = client.post(
        f"/api/v1/incidents/{incident.id}/approve-dispatch",
        json={"unit_id": unit.id, "dispatcher_id": "CIVILIAN_USER"},
    )
    assert resp_unauth.status_code == 403

    # Random unauthorized string rejected with 403
    resp_random = client.post(
        f"/api/v1/incidents/{incident.id}/approve-dispatch",
        json={"unit_id": unit.id, "dispatcher_id": "RANDOM_CALLER_99"},
    )
    assert resp_random.status_code == 403


# ===========================================================================
# BUG-02: Fabricated Speech Transcription Zero-Hallucination
# ===========================================================================
def test_bug_02_no_fabricated_transcript_on_silent_or_failed_audio(client, monkeypatch):
    wav_header = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )

    def mock_transcribe_silent(file_bytes, filename="call.wav"):
        return ("", "en", 0.0, "NO_SPEECH_DETECTED")

    monkeypatch.setattr("backend.app.api.audio.transcribe_audio_file", mock_transcribe_silent)

    files = {"file": ("actual_user_call.wav", io.BytesIO(wav_header), "audio/wav")}
    response = client.post("/api/v1/audio/transcribe", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["transcription_status"] == "NO_SPEECH_DETECTED"
    # Must NOT hallucinate the fake head-on collision
    assert "Head-on collision near Guntur RTC" not in data["transcript"]
    assert data["requires_human_review"] is True


# ===========================================================================
# BUG-03: Inaccurate ETA Calculation & Road-Network Circuity
# ===========================================================================
def test_bug_03_road_network_eta_metrics_and_freshness(db_session):
    incident = Incident(
        id="inc-eta-test-01",
        incident_number="INC-2026-ETA01",
        description="Testing road network circuity and freshness",
        category="TRAFFIC_ACCIDENT",
        status="ASSESSED",
        severity="LEVEL_2_HIGH",
        latitude=16.3067,
        longitude=80.4365,
        requires_human_review=False,
    )
    db_session.add(incident)
    db_session.commit()

    recom = match_candidate_units(db_session, incident)
    assert "freshness_timestamp" in recom
    assert len(recom["candidate_units"]) > 0

    first = recom["candidate_units"][0]
    # Direct vs Road distance
    assert first["road_distance_km"] >= first["distance_km"]
    assert "eta_source" in first
    assert "traffic_condition" in first
    assert first["eta_minutes"] >= 1.0


# ===========================================================================
# BUG-04: Strict Resource Capability and Eligibility Filtering
# ===========================================================================
def test_bug_04_strict_resource_capability_filtering():
    # 1. Police patrol is ineligible as primary medical transport for cardiac arrest
    eligible, priority, reason = is_unit_eligible(
        unit_type="POLICE_PATROL",
        category="MEDICAL_EMERGENCY",
        hazards=[],
        casualty_count=1,
    )
    assert eligible is False
    assert "Not certified" in reason

    # 2. Ambulance is eligible for medical emergency
    eligible_amb, priority_amb, _ = is_unit_eligible(
        unit_type="AMBULANCE",
        category="MEDICAL_EMERGENCY",
        hazards=[],
        casualty_count=1,
    )
    assert eligible_amb is True
    assert priority_amb == 0

    # 3. Fire truck is eligible for traffic accident with fuel leak
    eligible_fire, priority_fire, _ = is_unit_eligible(
        unit_type="FIRE_TRUCK",
        category="TRAFFIC_ACCIDENT",
        hazards=["fuel_leak"],
        casualty_count=1,
    )
    assert eligible_fire is True
    assert priority_fire == 1


# ===========================================================================
# BUG-05: Incident ID Concurrency & Atomic Sequences
# ===========================================================================
def test_bug_05_sequential_monotonic_incident_numbering(client):
    numbers = []
    for i in range(5):
        resp = client.post(
            "/api/v1/incidents",
            json={
                "description": f"Incident concurrency test sequence {i}",
                "latitude": 16.3067 + (i * 0.002),
                "longitude": 80.4365 + (i * 0.002),
            },
        )
        assert resp.status_code == 201
        numbers.append(resp.json()["incident_number"])

    # All numbers must be strictly distinct
    assert len(set(numbers)) == 5
    year = datetime.now(timezone.utc).year
    for num in numbers:
        assert num.startswith(f"INC-{year}-")


# ===========================================================================
# BUG-06: Incorrect Emergency Classification (Negation & Context)
# ===========================================================================
def test_bug_06_negation_handling_suppresses_false_escalation():
    # Caller reports accident, but explicitly negates critical factors
    transcript_negated = (
        "Two vehicles minor bumper scrape near Guntur circle, no unconscious people, "
        "no fire, no fuel leak, zero injuries, everyone is standing outside talking."
    )

    assessment = evaluate_deterministic_rules(
        raw_text=transcript_negated,
        extracted_data={
            "incident_type": "TRAFFIC_ACCIDENT",
            "casualty_count": 0,
            "hazards": [],
            "location_markers": ["guntur", "circle"],
            "missing_information": [],
            "severity": "LEVEL_3_MODERATE",
            "requires_human_review": False,
        },
    )

    # Must NOT escalate to LEVEL_1_CRITICAL because unconscious, fire, fuel leak were negated!
    assert assessment["severity"] != "LEVEL_1_CRITICAL"
    assert assessment["severity"] in ("LEVEL_2_HIGH", "LEVEL_3_MODERATE")

    # Verify structured facts captured negated indicators
    negated = assessment["structured_facts"].get("negated_indicators", [])
    assert any("unconscious" in ind or "fire" in ind or "fuel" in ind for ind in negated)


def test_bug_06_affirmed_critical_indicators_escalate_properly():
    # Non-negated critical emergency
    transcript_affirmed = (
        "Severe head-on collision on highway, driver is unconscious and pinned, active fuel leak!"
    )

    assessment = evaluate_deterministic_rules(
        raw_text=transcript_affirmed,
        extracted_data={
            "incident_type": "TRAFFIC_ACCIDENT",
            "casualty_count": 1,
            "hazards": ["fuel_leak", "trapped_persons"],
            "location_markers": ["highway"],
            "missing_information": [],
            "severity": "LEVEL_2_HIGH",
            "requires_human_review": False,
        },
    )

    # Must escalate to LEVEL_1_CRITICAL due to affirmed unconscious and pinned
    assert assessment["severity"] == "LEVEL_1_CRITICAL"
    assert assessment["requires_human_review"] is True
    triggers = assessment["structured_facts"].get("critical_triggers", [])
    assert "unconscious" in triggers or "pinned" in triggers


def test_bug_06_drill_context_validation():
    # Context indicates training drill
    transcript_drill = "This is station 4 mock drill training exercise, simulating a building fire, repeat: drill only."

    assessment = evaluate_deterministic_rules(
        raw_text=transcript_drill,
        extracted_data={
            "incident_type": "FIRE",
            "casualty_count": 0,
            "hazards": ["fire"],
            "location_markers": ["station 4"],
            "missing_information": [],
            "severity": "LEVEL_2_HIGH",
            "requires_human_review": False,
        },
    )

    # Drill must be flagged and not treated as a real disaster
    assert assessment["severity"] == "LEVEL_4_LOW"
    assert "CONTEXT_DRILL_OR_FALSE_ALARM" in assessment["uncertainty_flags"]
    assert assessment["requires_human_review"] is True
