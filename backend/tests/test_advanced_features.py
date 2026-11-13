"""
Test suite for advanced operational modules:
- Users & Roles API
- Facilities & Departments API
- GPS Telemetry & Geofencing API
- Notifications & Templates API
- AI Agent Execution Tracking API
"""

import pytest


def test_user_management_lifecycle(client):
    """Test user roles list and user creation."""
    # 1. Get roles
    resp = client.get("/api/v1/users/roles")
    assert resp.status_code == 200
    roles = resp.json()
    assert len(roles) >= 1
    role_id = roles[0]["id"]

    # 2. Create user
    new_user = {
        "username": "paramedic_john",
        "email": "john@smart112.test",
        "password": "Password123!",
        "full_name": "John Paramedic",
        "role_id": role_id,
        "is_active": True,
        "is_verified": True,
    }
    create_resp = client.post("/api/v1/users", json=new_user)
    assert create_resp.status_code == 201
    user_data = create_resp.json()
    assert user_data["username"] == "paramedic_john"
    assert user_data["email"] == "john@smart112.test"
    user_id = user_data["id"]

    # 3. Retrieve user
    get_resp = client.get(f"/api/v1/users/{user_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == user_id


def test_facility_and_department_management(client):
    """Test creating facilities and hospital departments."""
    # 1. Create a hospital facility
    facility_payload = {
        "name": "Guntur Government General Hospital",
        "facility_type": "HOSPITAL",
        "address": "Collectorate Road, Guntur, AP",
        "latitude": 16.3067,
        "longitude": 80.4365,
        "has_emergency": True,
        "has_icu": True,
        "bed_count": 500,
        "available_beds": 42,
    }
    resp = client.post("/api/v1/facilities", json=facility_payload)
    assert resp.status_code == 201
    facility = resp.json()
    facility_id = facility["id"]
    assert facility["name"] == "Guntur Government General Hospital"
    assert facility["has_icu"] is True

    # 2. Create a department under the hospital
    dept_payload = {
        "facility_id": facility_id,
        "name": "Trauma & Emergency Care",
        "department_type": "EMERGENCY",
        "specialist_count": 12,
        "bed_count": 50,
        "available_beds": 8,
        "has_24x7_service": True,
    }
    dept_resp = client.post("/api/v1/facilities/departments", json=dept_payload)
    assert dept_resp.status_code == 201
    dept = dept_resp.json()
    assert dept["department_type"] == "EMERGENCY"
    assert dept["available_beds"] == 8

    # 3. Query list of facilities
    list_resp = client.get("/api/v1/facilities")
    assert list_resp.status_code == 200
    facilities = list_resp.json()
    assert len(facilities) >= 1


def test_gps_reading_and_geofencing(client):
    """Test GPS telemetry ingestion and geofence registration."""
    # 1. Ingest GPS reading
    reading_payload = {
        "device_id": "GPS-UNIT-01",
        "unit_id": "unit-test-01",
        "latitude": 16.3067,
        "longitude": 80.4365,
        "speed_kmh": 45.2,
        "heading": 180.0,
        "accuracy_meters": 4.5,
    }
    resp = client.post("/api/v1/gps/readings", json=reading_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["device_id"] == "GPS-UNIT-01"
    assert data["latitude"] == 16.3067

    # 2. Create a Geofence
    geofence_payload = {
        "name": "Guntur District HQ Zone",
        "type": "CIRCLE",
        "coordinates": [{"lat": 16.3067, "lng": 80.4365, "radius_m": 1000}],
        "description": "Inner emergency district radius",
    }
    geo_resp = client.post("/api/v1/gps/geofences", json=geofence_payload)
    assert geo_resp.status_code == 201
    geofence = geo_resp.json()
    assert geofence["name"] == "Guntur District HQ Zone"


def test_notifications_lifecycle(client):
    """Test creating notification templates and sending notifications."""
    # 1. Create a notification template
    template_payload = {
        "name": "URGENT_DISPATCH_ALERT",
        "template_type": "ALERT",
        "subject": "Emergency Dispatch Order",
        "body": "Unit {unit_callsign} dispatched to {incident_category}",
        "channels": ["IN_APP"],
    }
    tmpl_resp = client.post("/api/v1/notifications/templates", json=template_payload)
    assert tmpl_resp.status_code == 201
    template = tmpl_resp.json()
    assert template["name"] == "URGENT_DISPATCH_ALERT"

    # 2. Send in-app notification
    notif_payload = {
        "recipient_id": "user-dispatcher-01",
        "notification_type": "ALERT",
        "title": "Level 1 Dispatch Active",
        "message": "Unit AMB-TEST-01 is en route to scene.",
        "priority": "HIGH",
        "requires_ack": True,
    }
    notif_resp = client.post("/api/v1/notifications", json=notif_payload)
    assert notif_resp.status_code == 201
    notif = notif_resp.json()
    assert notif["title"] == "Level 1 Dispatch Active"
    notif_id = notif["id"]

    # 3. Acknowledge notification
    ack_resp = client.post(f"/api/v1/notifications/{notif_id}/acknowledge?ack_notes=Acknowledged+by+Sarah")
    assert ack_resp.status_code == 200
    assert ack_resp.json()["is_acknowledged"] is True


def test_ai_agent_tracking(client):
    """Test AI agent execution lifecycle and trace recording."""
    # 1. Start agent execution
    exec_payload = {
        "agent_name": "TriageAgent",
        "agent_type": "NLU_EXTRACTION",
        "session_id": "session-112-test",
        "input_data": {"transcript": "Major crash on highway near bridge."},
    }
    resp = client.post("/api/v1/ai/tracking/executions", json=exec_payload)
    assert resp.status_code == 201
    execution = resp.json()
    exec_id = execution["id"]
    assert execution["agent_name"] == "TriageAgent"

    # 2. Record a trace step
    trace_payload = {
        "execution_id": exec_id,
        "step_number": 1,
        "step_name": "NER_AND_TRIAGE_SCORING",
        "status": "COMPLETED",
        "latency_ms": 120,
        "output_data": {"severity": "LEVEL_1_CRITICAL", "confidence": 0.95},
    }
    trace_resp = client.post(f"/api/v1/ai/tracking/executions/{exec_id}/traces", json=trace_payload)
    assert trace_resp.status_code == 201
    trace = trace_resp.json()
    assert trace["step_name"] == "NER_AND_TRIAGE_SCORING"
    assert trace["latency_ms"] == 120

    # 3. Query execution summary
    summary_resp = client.get(f"/api/v1/ai/tracking/executions/{exec_id}/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["execution_id"] == exec_id
    assert summary["trace_count"] == 1
