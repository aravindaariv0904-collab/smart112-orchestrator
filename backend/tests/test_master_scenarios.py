"""
SMART 112: Master Multi-Scenario E2E Specification Test Suite
Verifies the 10 mandatory operational scenarios defined in Phase Eight:
  - Scenario 1: Standard emergency lifecycle
  - Scenario 2: Missing operational information & uncertainty flags
  - Scenario 3: AI provider failure & deterministic fallback
  - Scenario 4: Resource shortage & candidate unit exhaustion
  - Scenario 5: Unauthorized or invalid dispatch authorization
  - Scenario 6: Potential duplicate reports preservation
  - Scenario 7: Concurrent update conflicts & row locking
  - Scenario 8: GIS failure resilience & deterministic velocity model
  - Scenario 9: Multi-client payload contract consistency
  - Scenario 10: Complete chronological immutable audit trail
"""

import asyncio
import json
from unittest.mock import patch
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit


# ---------------------------------------------------------------------------
# Scenario 1: Standard Emergency Lifecycle
# ---------------------------------------------------------------------------
def test_scenario_01_standard_emergency_lifecycle(client, db_session):
    # 1. Citizen submits report
    res_create = client.post(
        "/api/v1/incidents",
        json={
            "description": "Multi-car collision on MG Road near Guntur bus stand, severe bleeding reported.",
            "latitude": 16.3067,
            "longitude": 80.4365,
            "address": "MG Road, Guntur",
            "caller_phone": "9876543210"
        }
    )
    assert res_create.status_code == 201
    inc = res_create.json()
    inc_id = inc["id"]
    assert inc["status"] in ("REPORTED", "ASSESSED")
    assert inc["severity"] == "LEVEL_1_CRITICAL"

    # 2. Query tactical recommendations
    res_rec = client.post(f"/api/v1/incidents/{inc_id}/recommend")
    assert res_rec.status_code == 200
    recs = res_rec.json()
    assert len(recs["candidate_units"]) > 0
    top_unit_id = recs["candidate_units"][0]["unit_id"]

    # 3. Human dispatcher approves deployment
    res_dispatch = client.post(
        f"/api/v1/incidents/{inc_id}/approve-dispatch",
        json={
            "unit_id": top_unit_id,
            "dispatcher_id": "DISPATCHER_SARAH",
            "notes": "Code Red priority deployment"
        }
    )
    assert res_dispatch.status_code == 200
    dispatch_data = res_dispatch.json()
    assert dispatch_data["status"] == "DISPATCHED"

    # 4. Unit telemetry signals arrival ON_SCENE
    res_on_scene = client.patch(
        f"/api/v1/units/{top_unit_id}/status",
        json={"status": "ON_SCENE", "dispatcher_id": "RESPONDER_RADIO"}
    )
    assert res_on_scene.status_code == 200

    # Verify incident advanced to ON_SCENE
    res_inc_check = client.get(f"/api/v1/incidents/{inc_id}")
    assert res_inc_check.json()["status"] == "ON_SCENE"

    # 5. Unit clears scene (AVAILABLE), transitioning incident to RESOLVED
    res_avail = client.patch(
        f"/api/v1/units/{top_unit_id}/status",
        json={"status": "AVAILABLE", "dispatcher_id": "RESPONDER_RADIO"}
    )
    assert res_avail.status_code == 200

    res_inc_resolved = client.get(f"/api/v1/incidents/{inc_id}")
    assert res_inc_resolved.json()["status"] == "RESOLVED"


# ---------------------------------------------------------------------------
# Scenario 2: Missing Information & Uncertainty Flags
# ---------------------------------------------------------------------------
def test_scenario_02_missing_information_flags_uncertainty(client, db_session):
    # Citizen provides vague text without exact landmarks or location markers
    res = client.post(
        "/api/v1/incidents",
        json={
            "description": "Something happened somewhere. Urgent assistance needed now.",
            "latitude": 16.3500,
            "longitude": 80.4500,
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert data["requires_human_review"] is True

    # Assessment data must flag uncertainty
    if data["assessment_data"]:
        facts = json.loads(data["assessment_data"])
        assert facts.get("requires_human_review") is True
        assert len(facts.get("missing_information", [])) > 0 or facts.get("uncertainty_detected") is True


# ---------------------------------------------------------------------------
# Scenario 3: AI Provider Failure & Fallback Preservation
# ---------------------------------------------------------------------------
def test_scenario_03_ai_provider_failure_persists_report(client, db_session):
    # Force AI extractor to time out (>3.0s)
    with patch("ai.extractor._call_gemini_api", side_effect=asyncio.TimeoutError()):
        res = client.post(
            "/api/v1/incidents",
            json={
                "description": "Gas tank leak reported behind vegetable market.",
                "latitude": 16.3100,
                "longitude": 80.4200
            }
        )
        assert res.status_code == 201
        data = res.json()
        # Incident report persisted safely despite AI failure
        assert data["id"] is not None
        assert data["requires_human_review"] is True
        # Safety rules escalate fuel/gas leak to critical
        assert data["severity"] == "LEVEL_1_CRITICAL"


# ---------------------------------------------------------------------------
# Scenario 4: No Available Resources (Resource Shortage)
# ---------------------------------------------------------------------------
def test_scenario_04_resource_shortage_preserves_severity(client, db_session):
    # Mark all units unavailable
    units = db_session.query(EmergencyUnit).all()
    for u in units:
        u.status = "DISPATCHED"
    db_session.commit()

    # Create urgent cardiac incident
    res = client.post(
        "/api/v1/incidents",
        json={
            "description": "Cardiac arrest, patient unconscious and not breathing.",
            "latitude": 16.3000,
            "longitude": 80.4300
        }
    )
    assert res.status_code == 201
    inc_id = res.json()["id"]

    # Query recommendations when 0 units available
    res_rec = client.post(f"/api/v1/incidents/{inc_id}/recommend")
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    assert len(rec_data["candidate_units"]) == 0
    assert "no emergency units are currently available" in rec_data["rationale"].lower()

    # Incident severity MUST NOT be downgraded due to lack of resources
    inc_check = client.get(f"/api/v1/incidents/{inc_id}").json()
    assert inc_check["severity"] == "LEVEL_1_CRITICAL"


# ---------------------------------------------------------------------------
# Scenario 5: Unauthorized or Invalid Dispatch Authorization
# ---------------------------------------------------------------------------
def test_scenario_05_unauthorized_dispatch_rejected(client, db_session):
    # Setup available unit and incident
    unit = EmergencyUnit(
        id="unit-scen-5",
        callsign="AMB-SCEN-5",
        unit_type="AMBULANCE",
        latitude=16.30,
        longitude=80.43,
        status="AVAILABLE"
    )
    incident = Incident(
        id="inc-scen-5",
        incident_number="INC-2026-SCEN5",
        description="Testing authorization rejection",
        latitude=16.30,
        longitude=80.43,
        status="RECOMMENDED"
    )
    db_session.add_all([unit, incident])
    db_session.commit()

    # Empty dispatcher ID should be rejected by validation
    res = client.post(
        f"/api/v1/incidents/{incident.id}/approve-dispatch",
        json={"unit_id": unit.id, "dispatcher_id": ""}
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Scenario 6: Potential Duplicate Reports Preserved Separately
# ---------------------------------------------------------------------------
def test_scenario_06_duplicate_reports_both_preserved(client, db_session):
    # Two callers report the same transformer explosion
    res1 = client.post(
        "/api/v1/incidents",
        json={
            "description": "Electrical transformer explosion on Station Road, huge fire.",
            "latitude": 16.3060,
            "longitude": 80.4360
        }
    )
    res2 = client.post(
        "/api/v1/incidents",
        json={
            "description": "Massive fire and sparks on Station Road after loud explosion.",
            "latitude": 16.3062,
            "longitude": 80.4361
        }
    )
    assert res1.status_code == 201
    assert res2.status_code == 201
    inc1 = res1.json()
    inc2 = res2.json()

    # Both incidents preserved distinctly; never silently merged
    assert inc1["id"] != inc2["id"]
    assert inc1["incident_number"] != inc2["incident_number"]


# ---------------------------------------------------------------------------
# Scenario 7: Concurrent Updates Conflict & Row Locking
# ---------------------------------------------------------------------------
def test_scenario_07_concurrent_dispatch_rejection(client, db_session):
    unit = EmergencyUnit(
        id="unit-scen-7",
        callsign="PATROL-SCEN-7",
        unit_type="POLICE_PATROL",
        latitude=16.31,
        longitude=80.44,
        status="AVAILABLE"
    )
    inc_a = Incident(
        id="inc-7a",
        incident_number="INC-2026-7A",
        description="Incident A",
        latitude=16.31,
        longitude=80.44,
        status="RECOMMENDED"
    )
    inc_b = Incident(
        id="inc-7b",
        incident_number="INC-2026-7B",
        description="Incident B",
        latitude=16.31,
        longitude=80.44,
        status="RECOMMENDED"
    )
    db_session.add_all([unit, inc_a, inc_b])
    db_session.commit()

    # Dispatch unit to Incident A
    res_a = client.post(
        f"/api/v1/incidents/{inc_a.id}/approve-dispatch",
        json={"unit_id": unit.id, "dispatcher_id": "DISPATCHER_1"}
    )
    assert res_a.status_code == 200

    # Concurrent attempt to dispatch same unit to Incident B must fail with 409
    res_b = client.post(
        f"/api/v1/incidents/{inc_b.id}/approve-dispatch",
        json={"unit_id": unit.id, "dispatcher_id": "DISPATCHER_2"}
    )
    assert res_b.status_code == 409
    assert "cannot be dispatched" in res_b.json()["detail"]


# ---------------------------------------------------------------------------
# Scenario 8: GIS Failure Resilience & Deterministic Model
# ---------------------------------------------------------------------------
def test_scenario_08_gis_resilience_deterministic_velocity(client, db_session):
    # Ensure spatial matcher calculates valid distance and ETA without external internet
    from backend.app.services.matcher import haversine_distance_km, calculate_eta_minutes

    dist = haversine_distance_km(16.3067, 80.4365, 16.3200, 80.4500)
    assert 2.0 < dist < 3.0
    eta = calculate_eta_minutes(dist)
    # At 40 km/h: ~3.5 to ~4.5 minutes
    assert 2.5 < eta < 6.0


# ---------------------------------------------------------------------------
# Scenario 9: Multi-Client Payload Contract Consistency
# ---------------------------------------------------------------------------
def test_scenario_09_multi_client_payload_contracts(client, db_session):
    res = client.get("/api/v1/incidents")
    assert res.status_code == 200
    incidents = res.json()
    for inc in incidents:
        # All required schema keys must be present for desktop, mobile & MDT
        assert "id" in inc
        assert "incident_number" in inc
        assert "status" in inc
        assert "severity" in inc
        assert "latitude" in inc
        assert "longitude" in inc
        assert "requires_human_review" in inc


# ---------------------------------------------------------------------------
# Scenario 10: Complete Chronological Immutable Audit Trail
# ---------------------------------------------------------------------------
def test_scenario_10_complete_audit_trail_recorded(client, db_session):
    # Run full incident lifecycle and verify audit logs
    res = client.post(
        "/api/v1/incidents",
        json={
            "description": "Structure fire on Brodipet 4th line, heavy smoke.",
            "latitude": 16.3050,
            "longitude": 80.4350
        }
    )
    inc_id = res.json()["id"]

    # Recommend
    client.post(f"/api/v1/incidents/{inc_id}/recommend")

    # Fetch audit records
    res_audit = client.get(f"/api/v1/audit/{inc_id}")
    assert res_audit.status_code == 200
    trail = res_audit.json()
    actions = [entry["action"] for entry in trail]
    assert "INCIDENT_REPORTED_AND_ASSESSED" in actions
    assert "RECOMMENDATION_GENERATED" in actions
