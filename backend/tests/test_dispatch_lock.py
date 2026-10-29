from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit

def test_atomic_unit_dispatch_and_double_booking_prevention(client, db_session):
    # Ensure unit and incident exist
    unit = db_session.query(EmergencyUnit).filter(EmergencyUnit.id == "unit-test-01").first()
    if not unit:
        unit = EmergencyUnit(
            id="unit-test-01",
            callsign="AMB-TEST-01",
            unit_type="AMBULANCE",
            latitude=16.3067,
            longitude=80.4365,
            status="AVAILABLE"
        )
        db_session.add(unit)

    inc1 = Incident(
        id="inc-test-01",
        incident_number="INC-2026-TEST-01",
        description="Head-on collision, unconscious patient",
        category="TRAFFIC_ACCIDENT",
        status="RECOMMENDED",
        severity="LEVEL_1_CRITICAL",
        latitude=16.3067,
        longitude=80.4365,
        requires_human_review=True
    )
    db_session.add(inc1)
    db_session.commit()

    # 1. Dispatch available unit to incident
    response1 = client.post(
        "/api/v1/incidents/inc-test-01/approve-dispatch",
        json={
            "unit_id": "unit-test-01",
            "dispatcher_id": "DISPATCHER_SARAH",
            "notes": "Immediate deployment"
        }
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "DISPATCHED"
    assert data1["unit_id"] == "unit-test-01"

    # 2. Verify unit status is now DISPATCHED
    refreshed_unit = db_session.query(EmergencyUnit).filter(EmergencyUnit.id == "unit-test-01").first()
    assert refreshed_unit.status == "DISPATCHED"

    # 3. Second dispatch attempt for the same unit must be blocked (HTTP 409)
    inc2 = Incident(
        id="inc-test-02",
        incident_number="INC-2026-TEST-02",
        description="Second collision report",
        status="RECOMMENDED",
        severity="LEVEL_2_HIGH",
        latitude=16.3070,
        longitude=80.4370
    )
    db_session.add(inc2)
    db_session.commit()

    response2 = client.post(
        "/api/v1/incidents/inc-test-02/approve-dispatch",
        json={
            "unit_id": "unit-test-01",
            "dispatcher_id": "DISPATCHER_SARAH"
        }
    )
    assert response2.status_code == 409
    assert "cannot be dispatched" in response2.json()["detail"]
