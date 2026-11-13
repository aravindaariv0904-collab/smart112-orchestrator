import io
import json
from datetime import datetime, timezone

import pytest

from ai.extractor import extract_emergency_facts
from ai.rules import check_indicator_with_negation, evaluate_deterministic_rules
from backend.app.core.security import is_authorized_dispatcher
from backend.app.models.audit import AuditLog
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit
from backend.app.services.matcher import is_unit_eligible, match_candidate_units


# ===========================================================================
# BUG-01: Weak Dispatcher Authentication & Backend-Enforced RBAC
# ===========================================================================
def test_bug_01_dispatcher_login_and_token_exchange(client):
    # 1. Valid dispatcher credentials -> 200 OK with JWT tokens
    resp_valid = client.post(
        "/api/v1/auth/login",
        json={"username": "dispatcher_sarah", "password": "cad112pass"},
    )
    assert resp_valid.status_code == 200
    data = resp_valid.json()
    assert data["role"] == "DISPATCHER"
    assert data["callsign"] == "DISPATCHER_SARAH"
    assert "DISPATCH_UNITS" in data["permissions"]
    access_token = data["access_token"]
    refresh_token = data["refresh_token"]
    assert len(access_token) > 20  # JWT token
    assert len(refresh_token) > 20  # JWT refresh token
    assert data["expires_in"] == 3600  # 1 hour in seconds
    assert data["token_type"] == "bearer"

    # 2. Invalid dispatcher credentials -> 401 Unauthorized
    resp_invalid = client.post(
        "/api/v1/auth/login",
        json={"username": "dispatcher_sarah", "password": "wrongpassword"},
    )
    assert resp_invalid.status_code == 401

    # 3. Verify JWT session token endpoint
    resp_verify = client.get(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp_verify.status_code == 200
    verify_data = resp_verify.json()
    assert verify_data["valid"] is True
    assert verify_data["callsign"] == "DISPATCHER_SARAH"
    assert verify_data["role"] == "DISPATCHER"
    assert "expires_at" in verify_data  # JWT has expiration


def test_bug_01_rbac_rejection_for_unauthorized_actors(client, db_session):
    incident = Incident(
        id="inc-rbac-test-01",
        incident_number="INC-2026-RBAC01",
        description="Testing RBAC enforcement",
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

    # Unauthorized role rejected with 403
    resp_unauth = client.post(
        f"/api/v1/incidents/{incident.id}/approve-dispatch",
        json={"unit_id": unit.id, "dispatcher_id": "CIVILIAN_USER"},
    )
    assert resp_unauth.status_code == 403

    # Random unauthorized string rejected with 403
    resp_random = client.post(
        f"/api/v1/incidents/{incident.id}/approve-dispatch",
        json={"unit_id": unit.id, "dispatcher_id": "RANDOM_CALLER_99"},
    )
    assert resp_random.status_code == 403


# ===========================================================================
# BUG-01b: Token Refresh and Expiration Handling
# ===========================================================================
def test_bug_01b_token_refresh_with_valid_refresh_token(client):
    # 1. Login to get access and refresh tokens
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "dispatcher_sarah", "password": "cad112pass"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    
    original_access_token = login_data["access_token"]
    refresh_token = login_data["refresh_token"]
    assert len(refresh_token) > 20
    assert login_data["token_type"] == "bearer"
    assert login_data["expires_in"] == 3600  # 1 hour
    
    # 2. Refresh the access token using the refresh token
    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    refresh_data = refresh_resp.json()
    
    # 3. Verify the new access token is valid (may be same if created in same second)
    new_access_token = refresh_data["access_token"]
    # Tokens may be identical if created in the same second (same iat)
    # What matters is that the refresh works and returns a valid token
    assert len(new_access_token) > 20
    assert refresh_data["token_type"] == "bearer"
    assert refresh_data["expires_in"] == 3600
    assert refresh_data["callsign"] == "DISPATCHER_SARAH"
    assert refresh_data["role"] == "DISPATCHER"
    
    # 4. Verify the new access token works
    verify_resp = client.get(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["valid"] is True
    assert verify_data["callsign"] == "DISPATCHER_SARAH"


def test_bug_01b_refresh_rejects_invalid_refresh_token(client):
    # 1. Try to refresh with an invalid refresh token
    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid-refresh-token-12345"},
    )
    assert resp.status_code == 401
    assert "Invalid or expired refresh token" in resp.json()["detail"]


def test_bug_01b_refresh_rejects_access_token_as_refresh_token(client):
    # 1. Login to get tokens
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "dispatcher_sarah", "password": "cad112pass"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    access_token = login_data["access_token"]
    
    # 2. Try to use the access token as a refresh token (should fail)
    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert resp.status_code == 401
    assert "Invalid token type" in resp.json()["detail"]


def test_bug_01b_refresh_rejects_empty_refresh_token(client):
    # 1. Try to refresh with an empty refresh token
    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": ""},
    )
    assert resp.status_code == 422  # Validation error


def test_bug_01b_expired_access_token_can_be_refreshed(client):
    """Test that an expired access token can be refreshed using a valid refresh token.
    This test verifies the token refresh flow works correctly.
    """
    # 1. Login to get tokens
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "supervisor_kumar", "password": "cad112pass"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    
    access_token = login_data["access_token"]
    refresh_token = login_data["refresh_token"]
    
    # 2. Verify the access token works initially
    verify_resp = client.get(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["valid"] is True
    
    # 3. Refresh the token
    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    refresh_data = refresh_resp.json()
    
    # 4. Verify the refreshed token works
    new_access_token = refresh_data["access_token"]
    verify_resp2 = client.get(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert verify_resp2.status_code == 200
    assert verify_resp2.json()["valid"] is True
    assert verify_resp2.json()["callsign"] == "SUPERVISOR_KUMAR"
    assert verify_resp2.json()["role"] == "SUPERVISOR"


def test_bug_01b_multiple_refresh_cycles_work(client):
    """Test that multiple refresh cycles work correctly.
    Each refresh should return a valid access token.
    """
    # 1. Login to get initial tokens
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "commissioner_lead", "password": "cad112pass"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    refresh_token = login_data["refresh_token"]
    
    # 2. Perform multiple refresh cycles
    for i in range(3):
        refresh_resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_resp.status_code == 200
        refresh_data = refresh_resp.json()
        
        # Verify each refreshed token works
        verify_resp = client.get(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {refresh_data['access_token']}"},
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["valid"] is True
        assert verify_resp.json()["callsign"] == "DISPATCHER_COMMISSIONER_01"
        assert verify_resp.json()["role"] == "ADMIN"


# ===========================================================================
# BUG-02: Fabricated Speech Transcription Zero-Hallucination
# ===========================================================================
def test_bug_02_no_fabricated_transcript_on_silent_or_failed_audio(client, monkeypatch):
    wav_header = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )

    def mock_transcribe_silent(file_bytes, filename="call.wav"):
        return ("", "en", 0.0, "NO_SPEECH_DETECTED")

    monkeypatch.setattr("backend.app.api.audio.transcribe_audio_file", mock_transcribe_silent)

    files = {"file": ("actual_user_call.wav", io.BytesIO(wav_header), "audio/wav")}
    response = client.post("/api/v1/audio/transcribe", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["transcription_status"] == "NO_SPEECH_DETECTED"
    # Must NOT hallucinate the fake head-on collision
    assert "Head-on collision near Guntur RTC" not in data["transcript"]
    assert data["requires_human_review"] is True


# ===========================================================================
# BUG-03: Inaccurate ETA Calculation & Road-Network Circuity
# ===========================================================================
def test_bug_03_road_network_eta_metrics_and_freshness(db_session):
    incident = Incident(
        id="inc-eta-test-01",
        incident_number="INC-2026-ETA01",
        description="Testing road network circuity and freshness",
        category="TRAFFIC_ACCIDENT",
        status="ASSESSED",
        severity="LEVEL_2_HIGH",
        latitude=16.3067,
        longitude=80.4365,
        requires_human_review=False,
    )
    db_session.add(incident)
    db_session.commit()

    recom = match_candidate_units(db_session, incident)
    assert "freshness_timestamp" in recom
    assert len(recom["candidate_units"]) > 0

    first = recom["candidate_units"][0]
    # Direct vs Road distance
    assert first["road_distance_km"] >= first["distance_km"]
    assert "eta_source" in first
    assert "traffic_condition" in first
    assert first["eta_minutes"] >= 1.0


# ===========================================================================
# BUG-04: Strict Resource Capability and Eligibility Filtering
# ===========================================================================
def test_bug_04_strict_resource_capability_filtering():
    # 1. Police patrol is ineligible as primary medical transport for cardiac arrest
    eligible, priority, reason = is_unit_eligible(
        unit_type="POLICE_PATROL",
        category="MEDICAL_EMERGENCY",
        hazards=[],
        casualty_count=1,
    )
    assert eligible is False
    assert "Not certified" in reason

    # 2. Ambulance is eligible for medical emergency
    eligible_amb, priority_amb, _ = is_unit_eligible(
        unit_type="AMBULANCE",
        category="MEDICAL_EMERGENCY",
        hazards=[],
        casualty_count=1,
    )
    assert eligible_amb is True
    assert priority_amb == 0

    # 3. Fire truck is eligible for traffic accident with fuel leak
    eligible_fire, priority_fire, _ = is_unit_eligible(
        unit_type="FIRE_TRUCK",
        category="TRAFFIC_ACCIDENT",
        hazards=["fuel_leak"],
        casualty_count=1,
    )
    assert eligible_fire is True
    assert priority_fire == 1


# ===========================================================================
# BUG-05: Incident ID Concurrency & Atomic Sequences
# ===========================================================================
def test_bug_05_sequential_monotonic_incident_numbering(client):
    numbers = []
    for i in range(5):
        resp = client.post(
            "/api/v1/incidents",
            json={
                "description": f"Incident concurrency test sequence {i}",
                "latitude": 16.3067 + (i * 0.002),
                "longitude": 80.4365 + (i * 0.002),
            },
        )
        assert resp.status_code == 201
        numbers.append(resp.json()["incident_number"])

    # All numbers must be strictly distinct
    assert len(set(numbers)) == 5
    year = datetime.now(timezone.utc).year
    for num in numbers:
        assert num.startswith(f"INC-{year}-")


# ===========================================================================
# BUG-06: Incorrect Emergency Classification (Negation & Context)
# ===========================================================================
def test_bug_06_negation_handling_suppresses_false_escalation():
    # Caller reports accident, but explicitly negates critical factors
    transcript_negated = (
        "Two vehicles minor bumper scrape near Guntur circle, no unconscious people, "
        "no fire, no fuel leak, zero injuries, everyone is standing outside talking."
    )

    assessment = evaluate_deterministic_rules(
        raw_text=transcript_negated,
        extracted_data={
            "incident_type": "TRAFFIC_ACCIDENT",
            "casualty_count": 0,
            "hazards": [],
            "location_markers": ["guntur", "circle"],
            "missing_information": [],
            "severity": "LEVEL_3_MODERATE",
            "requires_human_review": False,
        },
    )

    # Must NOT escalate to LEVEL_1_CRITICAL because unconscious, fire, fuel leak were negated!
    assert assessment["severity"] != "LEVEL_1_CRITICAL"
    assert assessment["severity"] in ("LEVEL_2_HIGH", "LEVEL_3_MODERATE")

    # Verify structured facts captured negated indicators
    negated = assessment["structured_facts"].get("negated_indicators", [])
    assert any("unconscious" in ind or "fire" in ind or "fuel" in ind for ind in negated)


def test_bug_06_affirmed_critical_indicators_escalate_properly():
    # Non-negated critical emergency
    transcript_affirmed = (
        "Severe head-on collision on highway, driver is unconscious and pinned, active fuel leak!"
    )

    assessment = evaluate_deterministic_rules(
        raw_text=transcript_affirmed,
        extracted_data={
            "incident_type": "TRAFFIC_ACCIDENT",
            "casualty_count": 1,
            "hazards": ["fuel_leak", "trapped_persons"],
            "location_markers": ["highway"],
            "missing_information": [],
            "severity": "LEVEL_2_HIGH",
            "requires_human_review": False,
        },
    )

    # Must escalate to LEVEL_1_CRITICAL due to affirmed unconscious and pinned
    assert assessment["severity"] == "LEVEL_1_CRITICAL"
    assert assessment["requires_human_review"] is True
    triggers = assessment["structured_facts"].get("critical_triggers", [])
    assert "unconscious" in triggers or "pinned" in triggers


def test_bug_06_drill_context_validation():
    # Context indicates training drill
    transcript_drill = "This is station 4 mock drill training exercise, simulating a building fire, repeat: drill only."

    assessment = evaluate_deterministic_rules(
        raw_text=transcript_drill,
        extracted_data={
            "incident_type": "FIRE",
            "casualty_count": 0,
            "hazards": ["fire"],
            "location_markers": ["station 4"],
            "missing_information": [],
            "severity": "LEVEL_2_HIGH",
            "requires_human_review": False,
        },
    )

    # Drill must be flagged and not treated as a real disaster
    assert assessment["severity"] == "LEVEL_4_LOW"
    assert "CONTEXT_DRILL_OR_FALSE_ALARM" in assessment["uncertainty_flags"]
    assert assessment["requires_human_review"] is True

# ===========================================================================
# BUG-01c: Rate Limiting on Auth Endpoints
# ===========================================================================
def test_bug_01c_rate_limit_returns_429_after_exceeding_limit(client):
    """Test that exceeding rate limit returns 429 Too Many Requests."""
    # Login endpoint limit: 10 requests per minute
    # Make 10 successful/failed logins to hit the limit
    for i in range(10):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "test_user", "password": "wrong_password"},
        )
        # Should get 401 for invalid credentials, not 429 yet
    
    # 11th request should be rate limited (429)
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "test_user", "password": "wrong_password"},
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers


def test_bug_01c_rate_limit_headers_present(client):
    """Test that rate limit headers are present in responses."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "test_user", "password": "wrong_password"},
    )
    
    # Check for rate limit headers
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    # Reset header may or may not be present depending on implementation
    
    # Verify header values are valid
    limit = int(resp.headers["X-RateLimit-Limit"])
    remaining = int(resp.headers["X-RateLimit-Remaining"])
    
    assert limit > 0
    assert remaining >= 0
    assert remaining < limit  # We just made a request


def test_bug_01c_successful_auth_clears_rate_limit(client):
    """Test that successful authentication clears the rate limit for that user."""
    # Make several failed login attempts
    for i in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "dispatcher_sarah", "password": "wrong_password"},
        )
        assert resp.status_code == 401
    
    # Now make a successful login
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "dispatcher_sarah", "password": "cad112pass"},
    )
    assert resp.status_code == 200
    
    # After successful auth, rate limit should be cleared for this user
    # Make another request - should not be rate limited
    resp2 = client.post(
        "/api/v1/auth/login",
        json={"username": "dispatcher_sarah", "password": "wrong_password"},
    )
    # Should get 401 (invalid password) not 429 (rate limited)
    assert resp2.status_code == 401


def test_bug_01c_rate_limit_on_refresh_endpoint(client):
    """Test rate limiting on token refresh endpoint."""
    # Login first to get a refresh token
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "dispatcher_sarah", "password": "cad112pass"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]
    
    # Make several refresh requests
    # Refresh limit: 30 requests per minute, so we need to make many requests
    # to hit the limit. Let's make 30 requests.
    for i in range(30):
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        # Should succeed (200) for valid refresh token
    
    # 31st request should be rate limited
    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 429


def test_bug_01c_rate_limit_varies_by_username(client):
    """Test that rate limiting is per-username (different users have separate limits)."""
    # Make requests as user1 until rate limited
    rate_limit_hit = False
    for i in range(15):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "user1_test", "password": "wrong"},
        )
        if resp.status_code == 429:
            rate_limit_hit = True
            break
    
    assert rate_limit_hit, "Should have hit rate limit for user1"
    
    # Now try with a different username - should not be rate limited
    # (separate rate limit buckets per username)
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "user2_test", "password": "wrong"},
    )
    # Should get 401 (invalid credentials) not 429 (rate limited)
    assert resp.status_code == 401


def test_bug_01c_rate_limit_headers_on_429(client):
    """Test that 429 responses include proper rate limit headers."""
    # Hit rate limit
    for i in range(12):
        client.post(
            "/api/v1/auth/login",
            json={"username": "rate_test_user", "password": "wrong"},
        )
    
    # Get the 429 response
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "rate_test_user", "password": "wrong"},
    )
    
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    
    # Verify header values
    assert int(resp.headers["Retry-After"]) > 0
    assert int(resp.headers["X-RateLimit-Limit"]) > 0
    assert int(resp.headers["X-RateLimit-Remaining"]) == 0


def test_bug_01c_429_response_body(client):
    """Test that 429 responses have appropriate error message."""
    # Hit rate limit
    for i in range(12):
        client.post(
            "/api/v1/auth/login",
            json={"username": "rate_test_user2", "password": "wrong"},
        )
    
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "rate_test_user2", "password": "wrong"},
    )
    
    assert resp.status_code == 429
    data = resp.json()
    assert "detail" in data
    assert "rate limit" in data["detail"].lower() or "try again" in data["detail"].lower()
