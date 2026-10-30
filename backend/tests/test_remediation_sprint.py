import io
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from backend.app.core.config import settings
from backend.app.core.security import is_authorized_dispatcher, verify_dispatcher_token
from backend.app.models.audit import AuditLog
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit
from backend.app.services.matcher import (
    calculate_eta_minutes,
    haversine_distance_km,
    match_candidate_units,
)


# ===========================================================================
# 1. PROPER DISPATCHER AUTHENTICATION
# ===========================================================================
def test_is_authorized_dispatcher_logic():
    # Valid dispatch callsigns
    assert is_authorized_dispatcher("DISPATCHER_SARAH") is True
    assert is_authorized_dispatcher("DISPATCHER_COMMISSIONER_01") is True
    assert is_authorized_dispatcher("DSP-01") is True
    assert is_authorized_dispatcher("OPERATOR_12") is True
    assert is_authorized_dispatcher("COMMANDER_CHIEF") is True
    assert is_authorized_dispatcher("SYSTEM") is True
    assert is_authorized_dispatcher("AMB-GNT-01") is True  # field unit updating status

    # Explicit unauthorized roles
    assert is_authorized_dispatcher("CIVILIAN_USER") is False
    assert is_authorized_dispatcher("GUEST") is False
    assert is_authorized_dispatcher("CITIZEN") is False
    assert is_authorized_dispatcher("ANONYMOUS_CALLER") is False
    assert is_authorized_dispatcher("UNAUTHORIZED_ACTOR") is False
    assert is_authorized_dispatcher("") is False
    assert is_authorized_dispatcher(None) is False

    # Unrecognized arbitrary actor string without token
    assert is_authorized_dispatcher("HACKER_123") is False
    assert is_authorized_dispatcher("RANDOM_USER_42") is False

    # Authorized with valid Dispatcher Token
    assert is_authorized_dispatcher("OPERATOR_CUSTOM", token="smart112-dispatch-key-2026") is True
    # Invalid token with unauthorized role is rejected
    assert is_authorized_dispatcher("CIVILIAN_USER", token="smart112-dispatch-key-2026") is False
    assert is_authorized_dispatcher("HACKER_123", token="invalid-token") is False


def test_dispatcher_auth_rejection_at_endpoint(client, db_session):
    incident = Incident(
        id="inc-auth-test-01",
        incident_number="INC-2026-AUT01",
        description="Testing unauthorized actor rejection",
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

    # 1. Unrecognized actor without token -> 403 Forbidden
    resp_unrecognized = client.post(
        f"/api/v1/incidents/{incident.id}/approve-dispatch",
        json={"unit_id": unit.id, "dispatcher_id": "HACKER_EXTERNAL"},
    )
    assert resp_unrecognized.status_code == 403
    assert "not authorized" in resp_unrecognized.json()["detail"]

    # 2. Civilian / unauthorized role -> 403 Forbidden
    resp_civilian = client.post(
        f"/api/v1/incidents/{incident.id}/approve-dispatch",
        json={"unit_id": unit.id, "dispatcher_id": "CIVILIAN_USER"},
    )
    assert resp_civilian.status_code == 403

    # 3. Valid dispatcher callsign -> 200 OK
    resp_valid = client.post(
        f"/api/v1/incidents/{incident.id}/approve-dispatch",
        json={"unit_id": unit.id, "dispatcher_id": "DISPATCHER_SARAH"},
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["status"] == "DISPATCHED"

    # Verify audit log recorded auth_method
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.incident_id == incident.id, AuditLog.action == "DISPATCH_APPROVED")
        .first()
    )
    assert audit is not None
    details = json.loads(audit.details)
    assert details["auth_method"] == "ROLE_VERIFIED"


# ===========================================================================
# 2. SAFE AUDIO TRANSCRIPTION FAILURE HANDLING
# ===========================================================================
def test_audio_transcription_safe_failure_handling(client, monkeypatch):
    # Construct a valid WAV header with silence
    wav_header = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )

    # Simulate faster-whisper reporting NO_SPEECH_DETECTED
    def mock_transcribe_silent(file_bytes, filename="emergency_call.wav"):
        return ("", "en", 0.0, "NO_SPEECH_DETECTED")

    monkeypatch.setattr("backend.app.api.audio.transcribe_audio_file", mock_transcribe_silent)

    files = {"file": ("caller_silence.wav", io.BytesIO(wav_header), "audio/wav")}
    response = client.post("/api/v1/audio/transcribe", files=files)

    # Must return 200 OK, never 500 crash!
    assert response.status_code == 200
    data = response.json()
    assert data["transcription_status"] == "NO_SPEECH_DETECTED"
    assert data["requires_human_review"] is True
    assert "manual operator" in data["transcript"]
    assert "AUDIO_NO_SPEECH_DETECTED" in data["extracted_facts"]["uncertainty_flags"]


def test_audio_transcription_engine_unavailable_handled_safely(client, monkeypatch):
    wav_header = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )

    # Simulate model failure / unavailable library
    def mock_transcribe_unavailable(file_bytes, filename="emergency_call.wav"):
        return ("", "unknown", 0.0, "STT_UNAVAILABLE")

    monkeypatch.setattr("backend.app.api.audio.transcribe_audio_file", mock_transcribe_unavailable)

    files = {"file": ("call_broken.wav", io.BytesIO(wav_header), "audio/wav")}
    response = client.post("/api/v1/audio/transcribe", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["transcription_status"] == "STT_UNAVAILABLE"
    assert data["requires_human_review"] is True
    assert "AUDIO_STT_UNAVAILABLE" in data["extracted_facts"]["uncertainty_flags"]


# ===========================================================================
# 3. RELIABLE INCIDENT ID GENERATION
# ===========================================================================
def test_reliable_incident_id_monotonicity_and_uniqueness(client):
    # Ingest multiple sequential incidents
    created_ids = []
    created_numbers = []
    for i in range(3):
        res = client.post(
            "/api/v1/incidents",
            json={
                "description": f"Incident intake reliability test sequence {i}",
                "latitude": 16.3067 + (i * 0.01),
                "longitude": 80.4365 + (i * 0.01),
            },
        )
        assert res.status_code == 201
        body = res.json()
        created_ids.append(body["id"])
        created_numbers.append(body["incident_number"])

    # All numbers must be unique and properly prefixed
    assert len(set(created_numbers)) == len(created_numbers)
    for num in created_numbers:
        assert num.startswith(f"INC-{datetime.now(timezone.utc).year}-")


def test_reliable_incident_id_survives_gap(client, db_session):
    year = datetime.now(timezone.utc).year
    # Insert a manual high-sequence row
    db_session.add(
        Incident(
            id="inc-gap-test-99",
            incident_number=f"INC-{year}-0099",
            description="High sequence gap incident",
            category="TRAFFIC_ACCIDENT",
            status="ASSESSED",
            severity="LEVEL_3_MODERATE",
            latitude=16.3067,
            longitude=80.4365,
            requires_human_review=False,
        )
    )
    db_session.commit()

    # Next created incident must detect gap and allocate 0100
    res = client.post(
        "/api/v1/incidents",
        json={
            "description": "Next incident following gap",
            "latitude": 16.3500,
            "longitude": 80.4700,
        },
    )
    assert res.status_code == 201
    assert res.json()["incident_number"] == f"INC-{year}-0100"


# ===========================================================================
# 4. CORRECT EMERGENCY RESOURCE MATCHING
# ===========================================================================
def test_multi_hazard_resource_matching(db_session):
    # Incident with traffic collision AND fuel leak / trapped persons
    incident = Incident(
        id="inc-multi-hazard-01",
        incident_number="INC-2026-HAZ01",
        description="Head-on collision, two passengers trapped with active fuel leak",
        category="TRAFFIC_ACCIDENT",
        status="ASSESSED",
        severity="LEVEL_1_CRITICAL",
        latitude=16.3067,
        longitude=80.4365,
        requires_human_review=True,
        assessment_data=json.dumps({
            "incident_type": "TRAFFIC_ACCIDENT",
            "hazards": ["fuel_leak", "trapped_persons"],
            "casualty_count": 2,
        }),
    )
    db_session.add(incident)
    db_session.commit()

    recom = match_candidate_units(db_session, incident)
    assert len(recom["candidate_units"]) > 0
    top_unit = recom["candidate_units"][0]
    # Primary match for traffic accident remains AMBULANCE
    assert top_unit["type"] == "AMBULANCE"
    # Rationale acknowledges secondary fire truck evaluation for fuel leak
    assert "FIRE_TRUCK" in recom["rationale"] or "fuel_leak" in incident.description


def test_resource_shortage_alert_when_no_preferred_unit(db_session):
    # Ensure an alternative unit exists that is AVAILABLE (e.g. Police)
    db_session.add(
        EmergencyUnit(
            id="unit-pol-shortage",
            callsign="POL-GNT-99",
            unit_type="POLICE_PATROL",
            latitude=16.3070,
            longitude=80.4370,
            status="AVAILABLE",
        )
    )
    # Set all ambulances to BUSY / DISPATCHED
    db_session.query(EmergencyUnit).filter(EmergencyUnit.unit_type == "AMBULANCE").update(
        {EmergencyUnit.status: "DISPATCHED"}
    )
    db_session.commit()

    # Now create medical emergency incident
    incident = Incident(
        id="inc-shortage-01",
        incident_number="INC-2026-SHT01",
        description="Cardiac arrest patient, immediate CPR underway",
        category="MEDICAL_EMERGENCY",
        status="ASSESSED",
        severity="LEVEL_1_CRITICAL",
        latitude=16.3067,
        longitude=80.4365,
        requires_human_review=True,
    )
    db_session.add(incident)
    db_session.commit()

    recom = match_candidate_units(db_session, incident)
    assert recom["resource_deficit"] is True
    assert "RESOURCE DEFICIT ALERT" in recom["rationale"]
    # Still returns alternative cross-discipline available units (Police or Fire)
    assert len(recom["candidate_units"]) > 0


# ===========================================================================
# 5. HONEST ETA AND LOCATION HANDLING
# ===========================================================================
def test_unconfirmed_zero_coordinates_handling(db_session):
    # Coordinates (0.0, 0.0) - Null Island / unconfirmed location
    incident = Incident(
        id="inc-zero-loc-01",
        incident_number="INC-2026-ZLOC01",
        description="Caller frantic, disconnected before providing location",
        category="GENERAL_EMERGENCY",
        status="ASSESSED",
        severity="LEVEL_1_CRITICAL",
        latitude=0.0,
        longitude=0.0,
        requires_human_review=True,
    )
    db_session.add(incident)
    db_session.commit()

    recom = match_candidate_units(db_session, incident)
    assert recom["location_status"] == "UNCONFIRMED_COORDINATES"
    assert len(recom["candidate_units"]) == 0
    assert "unconfirmed (0, 0)" in recom["rationale"]


def test_out_of_district_regional_coordinates_flagged(db_session):
    # Location 200 km away in Hyderabad (17.3850, 78.4867)
    incident = Incident(
        id="inc-out-district-01",
        incident_number="INC-2026-OUT01",
        description="Regional highway incident far outside municipal jurisdiction",
        category="TRAFFIC_ACCIDENT",
        status="ASSESSED",
        severity="LEVEL_2_HIGH",
        latitude=17.3850,
        longitude=78.4867,
        requires_human_review=True,
    )
    db_session.add(incident)
    db_session.commit()

    recom = match_candidate_units(db_session, incident)
    assert recom["location_status"] == "OUT_OF_DISTRICT_REGIONAL"
    assert "exceed primary municipal district boundary" in recom["rationale"]
    if recom["candidate_units"]:
        first = recom["candidate_units"][0]
        assert first["road_distance_km"] > first["distance_km"]
        assert first["eta_confidence"] == "REGIONAL_ESTIMATE"
