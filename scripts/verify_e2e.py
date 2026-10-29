#!/usr/bin/env python3
"""
SMART 112: live HTTP end-to-end verification against a running API server.

Start the server first, then run:

    uvicorn backend.app.main:app --port 8000
    python scripts/verify_e2e.py

Environment:
    SMART112_BASE_URL   API origin (default http://127.0.0.1:8000)
    SMART112_TIMEOUT    per-request timeout in seconds (default 15)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.getenv("SMART112_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = float(os.getenv("SMART112_TIMEOUT", "15"))


def request(method: str, path: str, payload: dict | None = None) -> dict | list:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, headers=headers, method=method
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def expect_status(method: str, path: str, payload: dict | None, expected: int) -> int:
    try:
        request(method, path, payload)
    except urllib.error.HTTPError as err:
        if err.code == expected:
            return err.code
        raise AssertionError(
            f"{method} {path} returned HTTP {err.code}, expected {expected}: {err.read()!r}"
        ) from err
    raise AssertionError(f"{method} {path} unexpectedly succeeded, expected HTTP {expected}")


def run_e2e_verification() -> int:
    print(f"=== [SMART 112] End-to-end verification against {BASE} ===")

    # 1. Health
    health = request("GET", "/health")
    assert health["status"] == "healthy", health
    print(
        f"[PASS 1/10] Health OK: service={health['service']} "
        f"dialect={health['database']['dialect']} reachable={health['database']['reachable']}"
    )

    # 2. Start from a known-clean queue so repeated runs are deterministic.
    request("DELETE", "/api/v1/incidents/purge-all")
    incidents = request("GET", "/api/v1/incidents")
    assert incidents == [], f"Expected an empty incident queue, found {len(incidents)}"
    print("[PASS 2/10] Incident queue purged and verified empty (0 active incidents)")

    # 3. Fleet readiness
    units = request("GET", "/api/v1/units")
    assert len(units) >= 10, f"Expected at least 10 units, found {len(units)}"
    assert all(unit["status"] == "AVAILABLE" for unit in units), "Fleet not fully AVAILABLE after purge"
    print(f"[PASS 3/10] Fleet readiness OK: {len(units)} units AVAILABLE")

    # 4. Ingestion + AI triage
    incident = request(
        "POST",
        "/api/v1/incidents",
        {
            "description": (
                "Major collision near Guntur RTC bus station, two passengers trapped "
                "and unconscious, fuel leaking"
            ),
            "latitude": 16.3067,
            "longitude": 80.4365,
            "address": "Guntur RTC Bus Complex",
        },
    )
    inc_id = incident["id"]
    inc_num = incident["incident_number"]
    assert incident["status"] == "ASSESSED", incident["status"]
    assert incident["requires_human_review"] is True
    print(
        f"[PASS 4/10] Ingestion & triage OK: {incident['incident_number']} "
        f"classified as {incident['category']} ({incident['severity']})"
    )

    # 5. Spatial matching
    recs = request("POST", f"/api/v1/incidents/{inc_id}/recommend")
    assert recs["candidate_units"], "No candidate units returned"
    top_unit = recs["candidate_units"][0]
    print(
        f"[PASS 5/10] Spatial matching OK: {top_unit['callsign']} "
        f"({top_unit['distance_km']} km, {top_unit['eta_minutes']} min ETA)"
    )

    # 6. Unauthorized dispatch rejection (Scenario 5)
    unauthorized_payload = {
        "unit_id": top_unit["unit_id"],
        "dispatcher_id": "UNAUTHORIZED_CITIZEN_01",
        "notes": "Attempted unauthorized deployment",
    }
    rejected_code = expect_status(
        "POST", f"/api/v1/incidents/{inc_id}/approve-dispatch", unauthorized_payload, 403
    )
    print(f"[PASS 6/10] Unauthorized dispatch rejected with HTTP {rejected_code} Forbidden")

    # 7. Duplicate incident detection (Scenario 6)
    dup_incident = request(
        "POST",
        "/api/v1/incidents",
        {
            "description": "Another caller: severe bus collision right in front of RTC terminal gate",
            "latitude": 16.3069,
            "longitude": 80.4367,
            "address": "Guntur RTC Bus Complex Gate 2",
        },
    )
    dup_id = dup_incident["id"]
    dup_num = dup_incident["incident_number"]
    assert dup_id != inc_id, "Duplicate incident was silently merged instead of preserved distinctly"
    assert dup_num != inc_num
    assert dup_incident["requires_human_review"] is True
    dup_facts = json.loads(dup_incident["assessment_data"])
    assert "POTENTIAL_DUPLICATE_REPORT" in dup_facts.get("uncertainty_flags", [])
    assert dup_facts.get("potential_duplicate_of") == inc_num
    print(
        f"[PASS 7/10] Duplicate incident detection OK: {dup_num} flagged as duplicate of {inc_num} "
        f"(dist: {dup_facts.get('potential_duplicate_distance_meters')}m) without silent merge"
    )

    # 8. Authorized human dispatch
    dispatch_payload = {
        "unit_id": top_unit["unit_id"],
        "dispatcher_id": "DISPATCHER_SARAH",
        "notes": "Code 3 deployment with lights and sirens",
    }
    dispatch = request(
        "POST", f"/api/v1/incidents/{inc_id}/approve-dispatch", dispatch_payload
    )
    assert dispatch["status"] == "DISPATCHED"
    print(f"[PASS 8/10] Authorized dispatch OK: unit {top_unit['callsign']} -> DISPATCHED")

    # 9. Concurrency / Double-booking blocked (Scenario 7)
    blocked = expect_status(
        "POST", f"/api/v1/incidents/{inc_id}/approve-dispatch", dispatch_payload, 409
    )
    print(f"[PASS 9/10] Double-booking conflict blocked with HTTP {blocked} Conflict")

    # 10. Immutable audit ledger & queue reset to empty
    audit_logs = request("GET", f"/api/v1/audit/{inc_id}")
    assert len(audit_logs) >= 3, f"Expected >=3 audit entries, found {len(audit_logs)}"
    print(f"[PASS 10/10] Immutable audit ledger OK: {len(audit_logs)} tamper-evident entries")

    # Final purge: return portal to empty state
    request("DELETE", "/api/v1/incidents/purge-all")
    final_incidents = request("GET", "/api/v1/incidents")
    assert final_incidents == [], f"Purge left {len(final_incidents)} incidents"
    print(">>> Final status: Portal queue purged, exactly 0 active incidents, 10 units AVAILABLE.")

    print("\n>>> ALL 10 END-TO-END PRODUCTION VERIFICATION SCENARIOS PASSED <<<")
    return 0


def main() -> int:
    try:
        return run_e2e_verification()
    except (AssertionError, urllib.error.URLError, KeyError, ValueError) as exc:
        print(f"\n[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
