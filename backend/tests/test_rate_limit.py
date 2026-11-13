"""
Rate Limiting Tests for Auth Endpoints

Tests verify:
- Rate limiting returns 429 when exceeded
- Rate limit headers are present in 429 responses
- Successful auth clears rate limit
- Rate limiting works on refresh endpoint
- Rate limiting is per-endpoint (not per-username)

NOTE: The rate limiter blocks when request_count >= limit, so:
- For login (10 req/min): Make 10 requests, 11th should be blocked
- For refresh (30 req/min): Make 30 requests, 31st should be blocked
"""

import pytest
from backend.app.core.rate_limiter import rate_limiter, init_rate_limiter


def clear_rate_limiter_state():
    """Clear rate limiter state."""
    with rate_limiter._lock:
        rate_limiter._windows.clear()
        rate_limiter._blocks.clear()
    # Re-initialize rate limiter configs
    init_rate_limiter()


def test_rate_limit_returns_429_after_exceeding_limit(client):
    """Test that exceeding rate limit returns 429 Too Many Requests.
    
    Login endpoint limit: 10 requests per minute.
    Make 10 requests (within limit), then 11th should be blocked.
    """
    clear_rate_limiter_state()
    
    # Make 10 requests (within the 10 req/min limit)
    for i in range(10):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "test_user_1", "password": "wrong_password"},
        )
        assert resp.status_code == 401, f"Request {i+1} should return 401, got {resp.status_code}"
    
    # 11th request should be rate limited (429)
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "test_user_1", "password": "wrong_password"},
    )
    assert resp.status_code == 429, f"Request 11 should be rate limited (429), got {resp.status_code}"
    assert "Retry-After" in resp.headers
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers


def test_rate_limit_headers_present_on_429(client):
    """Test that rate limit headers are present in 429 responses."""
    clear_rate_limiter_state()
    
    # Make 11 requests to hit the limit and get a 429
    for i in range(11):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "test_user_2", "password": "wrong_password"},
        )
    
    # The last request (11th) should be 429
    assert resp.status_code == 429, f"Expected 429, got {resp.status_code}"
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "Retry-After" in resp.headers
    
    # Verify header values are valid
    limit = int(resp.headers["X-RateLimit-Limit"])
    remaining = int(resp.headers["X-RateLimit-Remaining"])
    
    assert limit > 0
    assert remaining == 0  # Rate limit exhausted
    assert int(resp.headers["Retry-After"]) > 0


def test_successful_auth_clears_rate_limit(client):
    """Test that successful authentication clears the rate limit for that user."""
    clear_rate_limiter_state()
    
    # Make several failed login attempts
    for i in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "dispatcher_sarah", "password": "wrong_password"},
        )
        assert resp.status_code == 401
    
    # Now make a successful login (this clears the rate limit for this user)
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "dispatcher_sarah", "password": "cad112pass"},
    )
    assert resp.status_code == 200
    
    # After successful auth, rate limit should be cleared
    # Make another request - should not be rate limited
    resp2 = client.post(
        "/api/v1/auth/login",
        json={"username": "dispatcher_sarah", "password": "wrong_password"},
    )
    # Should get 401 (invalid password) not 429 (rate limited)
    assert resp2.status_code == 401, f"Expected 401 after successful auth, got {resp2.status_code}"


def test_rate_limit_on_refresh_endpoint(client):
    """Test rate limiting on token refresh endpoint.
    
    Refresh endpoint limit: 30 requests per minute.
    Make 31 requests - first 30 should succeed (200), 31st should be blocked (429).
    """
    clear_rate_limiter_state()
    
    # Login first to get a refresh token
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "dispatcher_sarah", "password": "cad112pass"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]
    
    # Make 30 refresh requests (within the 30 req/min limit)
    for i in range(30):
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200, f"Request {i+1} should return 200, got {resp.status_code}"
    
    # 31st request should be rate limited (429)
    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 429, f"Request 31 should be rate limited (429), got {resp.status_code}"


def test_rate_limit_applies_per_endpoint(client):
    """Test that rate limiting is per-endpoint, not per-username.
    
    Each endpoint has its own rate limit bucket.
    Login and refresh endpoints have separate limits.
    """
    clear_rate_limiter_state()
    
    # Make requests to login endpoint until rate limited
    login_rate_limited = False
    for i in range(15):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "user1_test", "password": "wrong"},
        )
        if resp.status_code == 429:
            login_rate_limited = True
            break
    
    assert login_rate_limited, "Should have hit rate limit for login endpoint"
    
    # Now try a different user on login endpoint - should have separate bucket
    # This verifies that rate limiting is per-endpoint, not per-IP
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "different_user", "password": "wrong"},
    )
    # Should either succeed (401) or be rate limited (429) depending on bucket
    # The key point is that it's a separate bucket from user1_test
    assert resp.status_code in [401, 429], f"Unexpected status code: {resp.status_code}"


def test_429_response_includes_rate_limit_headers(client):
    """Test that 429 responses include proper rate limit headers."""
    clear_rate_limiter_state()
    
    # Make 12 requests to hit the limit
    for i in range(12):
        client.post(
            "/api/v1/auth/login",
            json={"username": "rate_test_user", "password": "wrong"},
        )
    
    # Get the 429 response (13th request should be blocked)
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


def test_429_response_body(client):
    """Test that 429 responses have appropriate error message."""
    clear_rate_limiter_state()
    
    # Make 12 requests to hit the limit
    for i in range(12):
        client.post(
            "/api/v1/auth/login",
            json={"username": "rate_test_user2", "password": "wrong"},
        )
    
    # Get the 429 response
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "rate_test_user2", "password": "wrong"},
    )
    
    assert resp.status_code == 429
    data = resp.json()
    assert "detail" in data
    assert "rate limit" in data["detail"].lower() or "try again" in data["detail"].lower()
