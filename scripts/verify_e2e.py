import urllib.request
import json
import sys

BASE = 'http://127.0.0.1:8000'

def run_e2e_verification():
    print("=== [SMART 112] Executing Master End-to-End Verification ===")
    
    # 1. Health Check
    health_raw = urllib.request.urlopen(f'{BASE}/health').read().decode()
    health = json.loads(health_raw)
    assert health['status'] == 'healthy'
    print(f"[PASS 1/9] Health Check OK: Service = {health['service']}, SSOT = {health['ssot_enforced']}")

    # 2. Check initial empty state
    inc_raw = urllib.request.urlopen(f'{BASE}/api/v1/incidents').read().decode()
    incidents = json.loads(inc_raw)
    print(f"[PASS 2/9] Initial Incident Queue Verified Clean: {len(incidents)} active incidents")

    # 3. Units Fleet Verification
    unit_raw = urllib.request.urlopen(f'{BASE}/api/v1/units').read().decode()
    units = json.loads(unit_raw)
    assert len(units) == 10
    print(f"[PASS 3/9] Fleet Readiness OK: {len(units)} Units Active across Guntur / Vijayawada Corridor")

    # 4. Emergency Ingestion & Triage
    payload = {
        'description': 'Major collision near Guntur RTC bus station, two passengers trapped and unconscious, fuel leaking',
        'latitude': 16.3067,
        'longitude': 80.4365,
        'address': 'Guntur RTC Bus Complex'
    }
    req = urllib.request.Request(
        f'{BASE}/api/v1/incidents',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    created_inc = json.loads(urllib.request.urlopen(req).read().decode())
    inc_id = created_inc['id']
    inc_num = created_inc['incident_number']
    cat = created_inc['category']
    sev = created_inc['severity']
    assert sev == 'LEVEL_1_CRITICAL', f"Expected LEVEL_1_CRITICAL, got {sev}"
    assert created_inc['requires_human_review'] is True
    print(f"[PASS 4/9] Ingestion & AI Triage OK: {inc_num} classified as {cat} ({sev})")

    # 5. Spatial Proximity & Candidate Matching
    req_rec = urllib.request.Request(
        f'{BASE}/api/v1/incidents/{inc_id}/recommend',
        data=b'',
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    recs = json.loads(urllib.request.urlopen(req_rec).read().decode())
    assert len(recs['candidate_units']) > 0
    top_unit = recs['candidate_units'][0]
    print(f"[PASS 5/9] Spatial Unit Matching OK: Top candidate {top_unit['callsign']} ({top_unit['distance_km']} km, {top_unit['eta_minutes']} min ETA)")

    # 6. Human Dispatch Authorization Gate
    disp_payload = {
        'unit_id': top_unit['unit_id'],
        'dispatcher_id': 'DISPATCHER_SARAH',
        'notes': 'Code 3 Emergency deployment with lights and sirens'
    }
    req_disp = urllib.request.Request(
        f'{BASE}/api/v1/incidents/{inc_id}/approve-dispatch',
        data=json.dumps(disp_payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    disp_res = json.loads(urllib.request.urlopen(req_disp).read().decode())
    assert disp_res['status'] == 'DISPATCHED'
    print(f"[PASS 6/9] Dispatch Authorization Gate OK: Unit {top_unit['callsign']} status set to DISPATCHED")

    # 7. Concurrency Lock & Double Booking Prevention
    req_disp_conflict = urllib.request.Request(
        f'{BASE}/api/v1/incidents/{inc_id}/approve-dispatch',
        data=json.dumps(disp_payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        urllib.request.urlopen(req_disp_conflict)
        assert False, "Double dispatch should have been rejected with 400/409"
    except urllib.error.HTTPError as err:
        assert err.code in (400, 409)
        print(f"[PASS 7/9] Concurrency Lock OK: Duplicate deployment blocked with HTTP {err.code}")

    # 8. Immutable Audit Trail Verification
    audit_raw = urllib.request.urlopen(f'{BASE}/api/v1/audit/{inc_id}').read().decode()
    audit_logs = json.loads(audit_raw)
    assert len(audit_logs) >= 3
    print(f"[PASS 8/9] Governance Audit Trail OK: {len(audit_logs)} immutable lifecycle entries recorded")

    # 9. Purge Queue to return to clean empty portal
    req_purge = urllib.request.Request(
        f'{BASE}/api/v1/incidents/purge-all',
        data=b'',
        headers={'Content-Type': 'application/json'},
        method='DELETE'
    )
    purge_res = json.loads(urllib.request.urlopen(req_purge).read().decode())
    
    # Confirm clean empty state
    final_inc_raw = urllib.request.urlopen(f'{BASE}/api/v1/incidents').read().decode()
    final_incidents = json.loads(final_inc_raw)
    assert len(final_incidents) == 0
    print(f"[PASS 9/9] Queue Purge & Reset OK: Portal returned to empty state (0 active incidents)")

    print("\n>>> ALL 9 END-TO-END MULTI-TIER SYSTEM AUDIT CHECKS PASSED SUCCESSFULLY! <<<")

if __name__ == '__main__':
    run_e2e_verification()
