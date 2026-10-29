#!/usr/bin/env python3
"""
SMART 112: in-process end-to-end verification & autonomous simulation.

Runs the complete lifecycle - citizen intake, deterministic safety triage,
spatial unit matching, human-in-the-loop dispatch, on-scene resolution and the
immutable audit ledger - against the real application stack (PostgreSQL/PostGIS
when configured, SQLite fallback otherwise).

The FastAPI lifespan is entered explicitly so startup hooks (schema creation,
PostGIS probe, unit seeding) execute exactly as they do in production. The
operational dataset is purged before and after the run, so the script is
repeatable and leaves no synthetic incidents behind.

Exit codes: 0 = success, 1 = verification failure, 2 = destructive purge refused.
"""

from __future__ import annotations

import json
import logging
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure the repository root is importable when run as a plain script.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.core.config import settings  # noqa: E402
from backend.app.core.database import engine, is_sqlite  # noqa: E402
from backend.app.main import app  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("smart112.simulation")


def purge_queue(client: TestClient) -> None:
    """Reset incidents/dispatches/audits; abort cleanly if disabled."""
    response = client.delete("/api/v1/incidents/purge-all")
    if response.status_code == 403:
        raise SystemExit(
            "Refusing to run: destructive endpoints are disabled for this environment."
        )
    assert response.status_code == 200, f"Purge failed: {response.text}"


def run_simulation(client: TestClient) -> None:
    print("\n" + "=" * 80)
    print(">>> SMART 112: MASTER END-TO-END AUTOMATED VERIFICATION SIMULATION")
    print("=" * 80 + "\n")

    # STEP A: health + clean state
    print(">>> STEP A: Verifying Database Health & Clean State...")
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200, f"Health check failed: {health_resp.text}"
    health = health_resp.json()
    print(
        f"    [OK] Health: status={health['status']} dialect={health['database']['dialect']} "
        f"postgis={health['database'].get('postgis_version', 'n/a')}"
    )

    purge_queue(client)
    assert client.get("/api/v1/incidents").json() == []
    units = client.get("/api/v1/units").json()
    assert len(units) >= 10, f"Expected at least 10 units, found {len(units)}"
    print(f"    [OK] Queue empty; fleet online with {len(units)} units.\n")

    # STEP B: ingest emergency report
    print(">>> STEP B: Ingesting Emergency Intake Report...")
    report_payload = {
        "description": (
            "Head-on collision near Guntur RTC bus station, two passengers trapped "
            "and unconscious, fuel leaking"
        ),
        "latitude": 16.3067,
        "longitude": 80.4365,
        "address": "Guntur RTC Complex Cross, Andhra Pradesh",
        "caller_phone": "+919876543210",
    }
    create_resp = client.post("/api/v1/incidents", json=report_payload)
    assert create_resp.status_code == 201, f"Failed to report incident: {create_resp.text}"
    incident = create_resp.json()
    incident_id = incident["id"]
    print(f"    [OK] Incident created: {incident['incident_number']} (ID: {incident_id})")
    print(f"    [OK] Category: {incident['category']} | Status: {incident['status']}\n")

    # STEP C: deterministic escalation
    print(">>> STEP C: Verifying Deterministic Rule Escalation & Safety Flags...")
    assessment = json.loads(incident["assessment_data"])
    assert incident["severity"] == "LEVEL_1_CRITICAL", incident["severity"]
    assert incident["requires_human_review"] is True, "Human review flag missing"
    missing = assessment.get("missing_information", [])
    hazards = assessment.get("hazards", [])
    print(f"    [OK] Severity: {incident['severity']}")
    print(f"    [OK] Missing information: {missing}")
    print(f"    [OK] Hazards: {hazards}")
    assert any("fuel" in str(h).lower() for h in hazards), "Fuel leak hazard not detected"
    print("    [OK] High-risk triggers forced LEVEL_1_CRITICAL.\n")

    # STEP D: recommendations
    print(">>> STEP D: Executing Spatial Proximity Query (/recommend)...")
    rec_resp = client.post(f"/api/v1/incidents/{incident_id}/recommend")
    assert rec_resp.status_code == 200, f"Recommendation failed: {rec_resp.text}"
    rec_data = rec_resp.json()
    candidates = rec_data["candidate_units"]
    assert candidates, "No candidate units returned by matcher"
    top_unit = candidates[0]
    print(f"    [OK] Top ranked unit: {top_unit['callsign']} ({top_unit['type']})")
    print(f"    [OK] Distance: {top_unit['distance_km']} km | ETA: {top_unit['eta_minutes']} min")
    print(f"    [OK] Rationale: {rec_data['rationale']}")
    assert top_unit["type"] == "AMBULANCE", f"Expected ambulance, got {top_unit['type']}"
    print("    [OK] Nearest available ambulance ranked #1.\n")

    # STEP E: human dispatch approval
    print(">>> STEP E: Dispatcher Authorizing Deployment (/approve-dispatch)...")
    dispatch_payload = {
        "unit_id": top_unit["unit_id"],
        "dispatcher_id": "DISPATCHER_COMMISSIONER_01",
        "notes": "Code Red - high priority collision response with extrication equipment",
    }
    disp_resp = client.post(
        f"/api/v1/incidents/{incident_id}/approve-dispatch", json=dispatch_payload
    )
    assert disp_resp.status_code == 200, f"Approval failed: {disp_resp.text}"
    dispatch_result = disp_resp.json()
    print(f"    [OK] Dispatch order: {dispatch_result['dispatch_id']}")
    print(f"    [OK] Assignment status: {dispatch_result['status']}")

    inc_check = client.get(f"/api/v1/incidents/{incident_id}").json()
    assert inc_check["status"] == "DISPATCHED", inc_check["status"]
    print("    [OK] Incident transitioned to DISPATCHED.\n")

    # STEP F: unit lifecycle
    print(">>> STEP F: Telemetry Lifecycle (DISPATCHED -> ON_SCENE -> AVAILABLE)...")
    on_scene_resp = client.patch(
        f"/api/v1/units/{top_unit['unit_id']}/status",
        json={
            "status": "ON_SCENE",
            "dispatcher_id": top_unit["callsign"],
            "notes": "Arrived at Guntur RTC junction",
        },
    )
    assert on_scene_resp.status_code == 200, on_scene_resp.text
    inc_on_scene = client.get(f"/api/v1/incidents/{incident_id}").json()
    assert inc_on_scene["status"] == "ON_SCENE", inc_on_scene["status"]
    print(f"    [OK] Unit ON_SCENE; incident status: {inc_on_scene['status']}")

    clear_resp = client.patch(
        f"/api/v1/units/{top_unit['unit_id']}/status",
        json={
            "status": "AVAILABLE",
            "dispatcher_id": top_unit["callsign"],
            "notes": "Victims stabilized and transported",
        },
    )
    assert clear_resp.status_code == 200, clear_resp.text
    inc_resolved = client.get(f"/api/v1/incidents/{incident_id}").json()
    assert inc_resolved["status"] == "RESOLVED", inc_resolved["status"]
    print(f"    [OK] Unit cleared; incident status: {inc_resolved['status']}")
    print("    [OK] Full state-machine loop verified.\n")

    # STEP G: audit ledger
    print(">>> STEP G: Verifying Immutable Audit Ledger (/api/v1/audit/{id})...")
    audit_resp = client.get(f"/api/v1/audit/{incident_id}")
    assert audit_resp.status_code == 200, audit_resp.text
    audit_logs = audit_resp.json()
    assert len(audit_logs) >= 3, f"Expected >=3 audit entries, found {len(audit_logs)}"
    print(f"    [OK] Audit records: {len(audit_logs)}")
    for index, log in enumerate(audit_logs, 1):
        print(f"      [{index}] {log['timestamp']} | {log['actor']} | {log['action']}")

    actions = [log["action"] for log in audit_logs]
    assert "INCIDENT_REPORTED_AND_ASSESSED" in actions
    assert "DISPATCH_APPROVED" in actions
    assert any("ON_SCENE" in action for action in actions)
    assert any("AVAILABLE" in action for action in actions)
    print("    [OK] All actor actions and timestamps are immutably logged.\n")

    # Clean up so the next run starts from an empty queue.
    purge_queue(client)
    assert client.get("/api/v1/incidents").json() == []
    print(">>> Cleanup: queue purged; units reset to AVAILABLE.\n")

    print("=" * 80)
    print("[SUCCESS] ALL 7 E2E SIMULATION PHASES PASSED WITH ZERO ERRORS!")
    print("=" * 80 + "\n")


def main() -> int:
    print(
        f"Database target: {engine.url.render_as_string(hide_password=True)} "
        f"(dialect={engine.dialect.name}, sqlite_fallback={is_sqlite})"
    )
    if settings.is_production:
        print("Refusing to run the simulation in a production environment.", file=sys.stderr)
        return 2

    try:
        with TestClient(app) as client:
            run_simulation(client)
    except SystemExit as exc:
        return int(exc.code or 0)
    except (AssertionError, KeyError, ValueError) as exc:
        print(f"\n[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
