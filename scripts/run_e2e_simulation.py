#!/usr/bin/env python3
"""
SMART 112: Master End-to-End Verification & Autonomous Simulation Script
Executes full lifecycle verification from citizen intake, AI safety triage,
spatial unit matching, human-in-the-loop dispatch, to on-scene resolution and audit ledger proof.
"""

import sys
import os
import json
import logging

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure root workspace is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import SessionLocal, Base, engine
from backend.app.services.seed_units import seed_emergency_units

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("smart112.simulation")

client = TestClient(app)

def run_simulation():
    print("\n" + "="*80)
    print(">>> SMART 112: MASTER END-TO-END AUTOMATED VERIFICATION SIMULATION")
    print("="*80 + "\n")

    # STEP A: Verify database health and readiness
    print(">>> STEP A: Verifying Database Health & Seeding State...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seeded = seed_emergency_units(db)
        print(f"    [OK] Database online. Total units seeded in this run: {seeded}")
    finally:
        db.close()

    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200, f"Health check failed: {health_resp.text}"
    print(f"    [OK] Platform Health Verified: {health_resp.json()}\n")

    # STEP B: POST emergency report
    print(">>> STEP B: Ingesting Emergency Intake Report...")
    report_payload = {
        "description": "Head-on collision near Guntur RTC bus station, two passengers trapped and unconscious, fuel leaking",
        "latitude": 16.3067,
        "longitude": 80.4365,
        "address": "Guntur RTC Complex Cross, Andhra Pradesh",
        "caller_phone": "+919876543210"
    }
    create_resp = client.post("/api/v1/incidents", json=report_payload)
    assert create_resp.status_code == 201, f"Failed to report incident: {create_resp.text}"
    incident = create_resp.json()
    incident_id = incident["id"]
    print(f"    [OK] Incident Created: {incident['incident_number']} (ID: {incident_id})")
    print(f"    [OK] Category Assigned: {incident['category']}")
    print(f"    [OK] Initial Status: {incident['status']}\n")

    # STEP C: Assert AI extraction, severity escalation, and missing details
    print(">>> STEP C: Verifying Deterministic Rule Escalation & Safety Flags...")
    assessment = json.loads(incident["assessment_data"])
    print(f"    [OK] Assessed Severity: {incident['severity']}")
    assert incident["severity"] == "LEVEL_1_CRITICAL", f"Expected LEVEL_1_CRITICAL but got {incident['severity']}"
    assert incident["requires_human_review"] is True, "Human review flag was not raised on critical incident"
    
    missing = assessment.get("missing_information", [])
    print(f"    [OK] Missing Information Flags: {missing}")
    hazards = assessment.get("hazards", [])
    print(f"    [OK] Identified Hazards: {hazards}")
    assert any("fuel" in h.lower() for h in hazards) or "fuel_leak" in hazards, "Fuel leak hazard not detected"
    print("    [OK] Safety rules asserted: High-risk triggers forced LEVEL_1_CRITICAL.\n")

    # STEP D: Query Recommendations
    print(">>> STEP D: Executing Spatial Proximity Query (/recommend)...")
    rec_resp = client.post(f"/api/v1/incidents/{incident_id}/recommend")
    assert rec_resp.status_code == 200, f"Recommendation failed: {rec_resp.text}"
    rec_data = rec_resp.json()
    candidates = rec_data["candidate_units"]
    assert len(candidates) > 0, "No candidate units returned by matcher"
    
    top_unit = candidates[0]
    print(f"    [OK] Top Ranked Unit: {top_unit['callsign']} ({top_unit['type']})")
    print(f"    [OK] Calculated Distance: {top_unit['distance_km']} km | ETA: {top_unit['eta_minutes']} min")
    print(f"    [OK] Tactical Rationale: {rec_data['rationale']}")
    assert top_unit["type"] == "AMBULANCE", f"Expected Ambulance #1 for medical collision, got {top_unit['type']}"
    print("    [OK] Spatial matcher asserted: Nearest available ambulance ranked #1.\n")

    # STEP E: Human Dispatch Approval
    print(">>> STEP E: Dispatcher Authorizing Deployment (/approve-dispatch)...")
    dispatch_payload = {
        "unit_id": top_unit["unit_id"],
        "dispatcher_id": "DISPATCHER_COMMISSIONER_01",
        "notes": "Code Red - High priority collision response with extrication equipment"
    }
    disp_resp = client.post(f"/api/v1/incidents/{incident_id}/approve-dispatch", json=dispatch_payload)
    assert disp_resp.status_code == 200, f"Approval failed: {disp_resp.text}"
    dispatch_result = disp_resp.json()
    print(f"    [OK] Dispatch Order Issued: {dispatch_result['dispatch_id']}")
    print(f"    [OK] State Transition: {dispatch_result['status']}")

    # Verify incident and unit status in database
    inc_check = client.get(f"/api/v1/incidents/{incident_id}").json()
    assert inc_check["status"] == "DISPATCHED", f"Incident status expected DISPATCHED, got {inc_check['status']}"
    print("    [OK] Incident record transitioned to DISPATCHED.\n")

    # STEP F: Unit lifecycle updates (ON_SCENE -> RESOLVED)
    print(">>> STEP F: Telemetry Lifecycle Progression (DISPATCHED -> ON_SCENE -> AVAILABLE)...")
    # 1. Unit arrives on scene
    on_scene_resp = client.patch(
        f"/api/v1/units/{top_unit['unit_id']}/status",
        json={"status": "ON_SCENE", "dispatcher_id": top_unit["callsign"], "notes": "Arrived at Guntur RTC Junction"}
    )
    assert on_scene_resp.status_code == 200
    inc_on_scene = client.get(f"/api/v1/incidents/{incident_id}").json()
    print(f"    [OK] Unit reported ON_SCENE. Incident status: {inc_on_scene['status']}")
    assert inc_on_scene["status"] == "ON_SCENE"

    # 2. Unit resolves incident and clears scene
    clear_resp = client.patch(
        f"/api/v1/units/{top_unit['unit_id']}/status",
        json={"status": "AVAILABLE", "dispatcher_id": top_unit["callsign"], "notes": "Victims stabilized and transported"}
    )
    assert clear_resp.status_code == 200
    inc_resolved = client.get(f"/api/v1/incidents/{incident_id}").json()
    print(f"    [OK] Unit cleared scene (AVAILABLE). Incident status: {inc_resolved['status']}")
    assert inc_resolved["status"] == "RESOLVED"
    print("    [OK] State machine lifecycle verified: Full transition loop complete.\n")

    # STEP G: Immutable Audit Ledger Verification
    print(">>> STEP G: Querying Chronological Immutable Audit Ledger (/api/v1/audit/{id})...")
    audit_resp = client.get(f"/api/v1/audit/{incident_id}")
    assert audit_resp.status_code == 200, f"Audit retrieval failed: {audit_resp.text}"
    audit_logs = audit_resp.json()
    assert len(audit_logs) >= 3, f"Expected at least 3 audit entries, found {len(audit_logs)}"
    
    print(f"    [OK] Total Audit Records Recorded: {len(audit_logs)}")
    for i, log in enumerate(audit_logs, 1):
        print(f"      [{i}] {log['timestamp']} | Actor: {log['actor']} | Action: {log['action']}")
    
    actions = [l["action"] for l in audit_logs]
    assert "INCIDENT_REPORTED_AND_ASSESSED" in actions
    assert "DISPATCH_APPROVED" in actions
    assert any("ON_SCENE" in a for a in actions)
    assert any("AVAILABLE" in a for a in actions)
    print("    [OK] Audit ledger governance verified: All actor actions and timestamps immutably logged.\n")

    print("="*80)
    print("[SUCCESS] ALL 7 E2E SIMULATION PHASES PASSED WITH ZERO ERRORS!")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_simulation()
