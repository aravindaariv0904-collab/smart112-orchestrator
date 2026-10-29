import io
import pytest
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit

@pytest.fixture
def seed_hardening_data(db_session):
    unit = EmergencyUnit(
        id="unit-sec-01",
        callsign="AMB-SEC-01",
        unit_type="AMBULANCE",
        latitude=16.3067,
        longitude=80.4365,
        status="AVAILABLE"
    )
    db_session.add(unit)

    incident = Incident(
        id="inc-sec-01",
        incident_number="INC-2026-SEC-01",
        description="Explosion at chemical warehouse",
        category="FIRE",
        status="ASSESSED",
        severity="LEVEL_1_CRITICAL",
        latitude=16.3067,
        longitude=80.4365,
        requires_human_review=True
    )
    db_session.add(incident)
    db_session.commit()
    return unit, incident

def test_missing_incident_404(client, seed_hardening_data):
    res = client.get("/api/v1/incidents/non-existent-id")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

def test_missing_unit_404_on_dispatch(client, seed_hardening_data):
    res = client.post(
        "/api/v1/incidents/inc-sec-01/approve-dispatch",
        json={"unit_id": "non-existent-unit", "dispatcher_id": "DISPATCHER_TOM"}
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

def test_dispatch_confirm_alias_endpoint(client, db_session, seed_hardening_data):
    res = client.post(
        "/api/v1/dispatch/confirm",
        json={
            "incident_id": "inc-sec-01",
            "unit_id": "unit-sec-01",
            "dispatcher_id": "DISPATCHER_JANE",
            "notes": "Code Red Deployment"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "DISPATCHED"
    assert data["unit_id"] == "unit-sec-01"

    # Subsequent dispatch on already dispatched unit returns 409
    res_conflict = client.post(
        "/api/v1/dispatch/confirm",
        json={
            "incident_id": "inc-sec-01",
            "unit_id": "unit-sec-01",
            "dispatcher_id": "DISPATCHER_JANE"
        }
    )
    assert res_conflict.status_code == 409
    assert "cannot be dispatched" in res_conflict.json()["detail"]

def test_illegal_state_transition_400(client, db_session, seed_hardening_data):
    # First dispatch
    client.post(
        "/api/v1/dispatch/confirm",
        json={"incident_id": "inc-sec-01", "unit_id": "unit-sec-01", "dispatcher_id": "DISPATCHER_JANE"}
    )
    # Reset unit to available to isolate incident state error
    unit = db_session.query(EmergencyUnit).filter(EmergencyUnit.id == "unit-sec-01").first()
    unit.status = "AVAILABLE"
    db_session.commit()

    # Re-dispatching an already DISPATCHED incident violates state machine -> 400
    res_invalid = client.post(
        "/api/v1/incidents/inc-sec-01/approve-dispatch",
        json={"unit_id": "unit-sec-01", "dispatcher_id": "DISPATCHER_JANE"}
    )
    assert res_invalid.status_code == 400
    assert "Illegal state transition" in res_invalid.json()["detail"]

def test_audit_log_immutability(client, seed_hardening_data):
    # Verify GET works
    res_get = client.get("/api/v1/audit/inc-sec-01")
    assert res_get.status_code == 200
    assert isinstance(res_get.json(), list)

    # Verify PUT, PATCH, DELETE are not allowed on audit logs
    res_put = client.put("/api/v1/audit/inc-sec-01", json={"action": "MUTATED"})
    assert res_put.status_code in [404, 405]

    res_patch = client.patch("/api/v1/audit/inc-sec-01", json={"action": "MUTATED"})
    assert res_patch.status_code in [404, 405]

    res_delete = client.delete("/api/v1/audit/inc-sec-01")
    assert res_delete.status_code in [404, 405]

def test_input_sanitization_strips_xss(client):
    res = client.post(
        "/api/v1/incidents",
        json={
            "description": "<script>alert('xss')</script>Two car crash near junction",
            "latitude": 16.3067,
            "longitude": 80.4365,
            "address": "<img src=x onerror=alert(1)> Main Road"
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert "<script>" not in data["description"]
    assert "<img" not in data["address"]
    assert "Two car crash" in data["description"]
    assert "Main Road" in data["address"]

def test_audio_upload_mime_and_size_validation(client):
    # 1. Reject invalid MIME type
    text_file = io.BytesIO(b"Not an audio file")
    res_bad_mime = client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("malicious.exe", text_file, "application/x-msdownload")}
    )
    assert res_bad_mime.status_code == 400
    assert "Unsupported media type" in res_bad_mime.json()["detail"]

    # 2. Reject empty audio file
    empty_file = io.BytesIO(b"")
    res_empty = client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("empty.wav", empty_file, "audio/wav")}
    )
    assert res_empty.status_code == 400
    assert "empty" in res_empty.json()["detail"].lower()

    # 3. Accept valid audio file
    valid_file = io.BytesIO(b"RIFF....WAVEfmt ....data....")
    res_valid = client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("call.wav", valid_file, "audio/wav")}
    )
    assert res_valid.status_code == 200
    data = res_valid.json()
    assert "transcript" in data
    assert "extracted_facts" in data


def test_unauthorized_dispatcher_rejected_with_403(client, db_session, seed_hardening_data):
    """Scenario 5: Non-dispatcher / unauthorized actors must receive 403 Forbidden."""
    unauthorized_actors = [
        "UNAUTHORIZED_USER",
        "GUEST",
        "CITIZEN",
        "CIVILIAN",
        "ANONYMOUS",
        "EXTERNAL_UNAUTHORIZED_ACTOR",
    ]
    for actor in unauthorized_actors:
        res = client.post(
            "/api/v1/incidents/inc-sec-01/approve-dispatch",
            json={"unit_id": "unit-sec-01", "dispatcher_id": actor},
        )
        assert res.status_code == 403, f"Expected 403 for {actor}, got {res.status_code}"
        assert "not authorized" in res.json()["detail"].lower()

    # Also test via /api/v1/dispatch/confirm
    res_confirm = client.post(
        "/api/v1/dispatch/confirm",
        json={
            "incident_id": "inc-sec-01",
            "unit_id": "unit-sec-01",
            "dispatcher_id": "UNAUTHORIZED_GUEST_112",
        },
    )
    assert res_confirm.status_code == 403
    assert "not authorized" in res_confirm.json()["detail"].lower()


def test_duplicate_incident_detection_flagged_without_silent_merge(client, db_session):
    """Scenario 6: Reports within 250m & 30m window are flagged as duplicates but preserved distinctly."""
    import json

    # 1. First caller reports an accident
    res1 = client.post(
        "/api/v1/incidents",
        json={
            "description": "Multi-car collision on ring road with fuel leak",
            "latitude": 16.3067,
            "longitude": 80.4365,
            "address": "Ring Road Junction",
        },
    )
    assert res1.status_code == 201
    inc1 = res1.json()
    inc1_id = inc1["id"]
    inc1_num = inc1["incident_number"]

    # 2. Second caller reports from ~50m away at the same junction
    res2 = client.post(
        "/api/v1/incidents",
        json={
            "description": "Second caller: huge accident on ring road, car smoking",
            "latitude": 16.3069,
            "longitude": 80.4367,
            "address": "Ring Road Junction near signal",
        },
    )
    assert res2.status_code == 201
    inc2 = res2.json()
    inc2_id = inc2["id"]
    inc2_num = inc2["incident_number"]

    # 3. Verify they are separate, distinct records (NO silent merge)
    assert inc1_id != inc2_id
    assert inc1_num != inc2_num

    # 4. Verify duplicate detection flagged incident 2
    assert inc2["requires_human_review"] is True
    assessment2 = json.loads(inc2["assessment_data"])
    assert "POTENTIAL_DUPLICATE_REPORT" in assessment2.get("uncertainty_flags", [])
    assert assessment2.get("potential_duplicate_of") == inc1_num
    assert assessment2.get("potential_duplicate_id") == inc1_id
    assert assessment2.get("potential_duplicate_distance_meters", 999) < 250

    # 5. Third report far away (5 km away) is NOT flagged as duplicate
    res3 = client.post(
        "/api/v1/incidents",
        json={
            "description": "Medical emergency at suburban clinic",
            "latitude": 16.3500,
            "longitude": 80.4800,
            "address": "Suburban Clinic",
        },
    )
    assert res3.status_code == 201
    inc3 = res3.json()
    assessment3 = json.loads(inc3["assessment_data"])
    assert "POTENTIAL_DUPLICATE_REPORT" not in assessment3.get("uncertainty_flags", [])

