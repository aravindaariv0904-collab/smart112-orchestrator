"""
SMART 112: Fixture-Driven Validation Tests
Verifies that all mock sample payloads in sample_data/ accurately represent the domain
and execute successfully against the authoritative backend state machine.
"""

import json
from pathlib import Path
import pytest
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data"


def load_fixture(filename: str):
    file_path = FIXTURES_DIR / filename
    assert file_path.exists(), f"Missing fixture file: {file_path}"
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_fixture_files_exist_and_parse():
    """Ensure all sample fixtures exist and are valid JSON."""
    incidents = load_fixture("sample_incidents.json")
    assert isinstance(incidents, list) and len(incidents) >= 4

    units = load_fixture("sample_units.json")
    assert isinstance(units, list) and len(units) >= 5

    orders = load_fixture("sample_dispatch_orders.json")
    assert "valid_dispatch_approval" in orders
    assert "unauthorized_dispatch_attempt" in orders

    assessments = load_fixture("sample_triage_assessments.json")
    assert "nominal_ai_assessment" in assessments
    assert "ai_timeout_fallback_assessment" in assessments


def test_happy_path_standard_lifecycle_from_sample_data(client, db_session):
    """
    Happy path:
    1. Ingest sample incident 0 (Critical collision with fuel leak).
    2. Confirm severity LEVEL_1_CRITICAL and human review required.
    3. Generate recommendations.
    4. Approve dispatch with authorized dispatcher.
    5. Progress unit to ON_SCENE and AVAILABLE (RESOLVED).
    """
    sample_incidents = load_fixture("sample_incidents.json")
    primary_sample = sample_incidents[0]

    # 1. Ingest incident
    create_resp = client.post(
        "/api/v1/incidents",
        json={
            "description": primary_sample["description"],
            "latitude": primary_sample["latitude"],
            "longitude": primary_sample["longitude"],
            "address": primary_sample["address"],
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    incident_id = created["id"]
    assert created["severity"] == "LEVEL_1_CRITICAL"
    assert created["category"] == "TRAFFIC_ACCIDENT"
    assert created["requires_human_review"] is True

    # 2. Get recommendations
    rec_resp = client.post(f"/api/v1/incidents/{incident_id}/recommend")
    assert rec_resp.status_code == 200
    recs = rec_resp.json()
    assert len(recs["candidate_units"]) > 0
    assigned_unit_id = recs["candidate_units"][0]["unit_id"]

    # 3. Approve dispatch using sample order payload
    sample_orders = load_fixture("sample_dispatch_orders.json")
    dispatch_payload = sample_orders["valid_dispatch_approval"]

    dispatch_resp = client.post(
        f"/api/v1/incidents/{incident_id}/approve-dispatch",
        json={
            "unit_id": assigned_unit_id,
            "dispatcher_id": dispatch_payload["dispatcher_id"],
            "notes": dispatch_payload["notes"],
        },
    )
    assert dispatch_resp.status_code == 200
    assert dispatch_resp.json()["status"] == "DISPATCHED"

    # 4. Progress unit through lifecycle: ON_SCENE -> AVAILABLE
    scene_update = sample_orders["unit_status_on_scene"]
    on_scene_resp = client.patch(
        f"/api/v1/units/{assigned_unit_id}/status",
        json={
            "status": scene_update["status"],
            "dispatcher_id": scene_update["dispatcher_id"],
            "notes": scene_update["notes"],
        },
    )
    assert on_scene_resp.status_code == 200

    inc_check = client.get(f"/api/v1/incidents/{incident_id}")
    assert inc_check.json()["status"] == "ON_SCENE"

    resolved_update = sample_orders["unit_status_resolved"]
    clear_resp = client.patch(
        f"/api/v1/units/{assigned_unit_id}/status",
        json={
            "status": resolved_update["status"],
            "dispatcher_id": resolved_update["dispatcher_id"],
            "notes": resolved_update["notes"],
        },
    )
    assert clear_resp.status_code == 200

    inc_final = client.get(f"/api/v1/incidents/{incident_id}")
    assert inc_final.json()["status"] == "RESOLVED"


def test_edge_case_missing_information_uncertainty(client, db_session):
    """
    Edge case 1:
    Ingest sample incident with vague description and missing landmarks.
    Verify uncertainty diagnostics and missing information flags are raised.
    """
    sample_incidents = load_fixture("sample_incidents.json")
    vague_sample = sample_incidents[3]  # INC-2026-0004

    resp = client.post(
        "/api/v1/incidents",
        json={
            "description": vague_sample["description"],
            "latitude": vague_sample["latitude"],
            "longitude": vague_sample["longitude"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["requires_human_review"] is True
    assessment = json.loads(data["assessment_data"])
    assert len(assessment.get("missing_information", [])) > 0


def test_edge_case_duplicate_detection_preserves_records(client, db_session):
    """
    Edge case 2:
    Ingest an initial incident, then ingest a duplicate incident within 250m.
    Verify both records are preserved (no silent merge) and duplicate flag is set.
    """
    sample_incidents = load_fixture("sample_incidents.json")
    orig_sample = sample_incidents[0]
    dup_sample = sample_incidents[4]  # RTC Gate 2 (30m away)

    resp_orig = client.post(
        "/api/v1/incidents",
        json={
            "description": orig_sample["description"],
            "latitude": orig_sample["latitude"],
            "longitude": orig_sample["longitude"],
            "address": orig_sample["address"],
        },
    )
    assert resp_orig.status_code == 201
    orig_num = resp_orig.json()["incident_number"]

    resp_dup = client.post(
        "/api/v1/incidents",
        json={
            "description": dup_sample["description"],
            "latitude": dup_sample["latitude"],
            "longitude": dup_sample["longitude"],
            "address": dup_sample["address"],
        },
    )
    assert resp_dup.status_code == 201
    dup_data = resp_dup.json()
    assert dup_data["id"] != resp_orig.json()["id"]
    assert dup_data["incident_number"] != orig_num
    assert dup_data["requires_human_review"] is True

    dup_assessment = json.loads(dup_data["assessment_data"])
    assert "POTENTIAL_DUPLICATE_REPORT" in dup_assessment.get("uncertainty_flags", [])
    assert dup_assessment.get("potential_duplicate_of") == orig_num


def test_edge_case_unauthorized_dispatch_rejection(client, db_session):
    """
    Edge case 3:
    Attempt dispatch approval with unauthorized dispatcher identity.
    Verify backend rejects with HTTP 403 Forbidden.
    """
    sample_incidents = load_fixture("sample_incidents.json")
    inc_resp = client.post(
        "/api/v1/incidents",
        json={
            "description": sample_incidents[1]["description"],
            "latitude": sample_incidents[1]["latitude"],
            "longitude": sample_incidents[1]["longitude"],
        },
    )
    assert inc_resp.status_code == 201
    inc_id = inc_resp.json()["id"]

    sample_orders = load_fixture("sample_dispatch_orders.json")
    unauth = sample_orders["unauthorized_dispatch_attempt"]

    # Locate any available unit
    unit = db_session.query(EmergencyUnit).filter(EmergencyUnit.status == "AVAILABLE").first()
    assert unit is not None

    unauth_resp = client.post(
        f"/api/v1/incidents/{inc_id}/approve-dispatch",
        json={
            "unit_id": unit.id,
            "dispatcher_id": unauth["dispatcher_id"],
            "notes": unauth["notes"],
        },
    )
    assert unauth_resp.status_code == 403
    assert "Forbidden" in unauth_resp.json()["detail"] or "unauthorized" in unauth_resp.json()["detail"].lower()
