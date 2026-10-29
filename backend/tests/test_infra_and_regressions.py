"""Infrastructure contract tests + regression tests for audit findings.

These tests are hermetic: they never touch the live PostGIS container, they only
assert on repository files and on the API surface backed by the SQLite test session.
"""
import re
from datetime import datetime, timezone
from pathlib import Path


from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Deliverable 1: docker-compose.yml contract
# ---------------------------------------------------------------------------
def test_compose_declares_postgis_16_image():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "image: postgis/postgis:16-3.4-alpine" in compose


def test_compose_exposes_expected_port_and_credentials():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    # Host port defaults to 5432 but stays overridable for port conflicts.
    assert re.search(r'"?\$\{POSTGRES_HOST_PORT:-5432\}:5432"?', compose)
    assert "POSTGRES_USER: ${POSTGRES_USER:-postgres}" in compose
    assert "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}" in compose
    assert "POSTGRES_DB: ${POSTGRES_DB:-smart112}" in compose


def test_compose_persists_pgdata_volume():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "pgdata:/var/lib/postgresql/data" in compose
    assert re.search(r"^volumes:\s*$", compose, re.MULTILINE)
    assert re.search(r"^  pgdata:\s*$", compose, re.MULTILINE)


def test_compose_ships_postgis_bootstrap_script():
    init_sql = REPO_ROOT / "scripts" / "postgres" / "init" / "01-postgis.sql"
    assert init_sql.is_file()
    assert "CREATE EXTENSION IF NOT EXISTS postgis;" in init_sql.read_text(encoding="utf-8")


def test_compose_healthcheck_verifies_postgis():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "pg_isready" in compose
    assert "pg_extension" in compose and "postgis" in compose
    assert "start_period" in compose


# ---------------------------------------------------------------------------
# Deliverable 4: scripts/healthcheck.sh
# ---------------------------------------------------------------------------
def test_healthcheck_script_contract():
    script = REPO_ROOT / "scripts" / "healthcheck.sh"
    assert script.is_file(), "scripts/healthcheck.sh is a required deliverable"
    content = script.read_text(encoding="utf-8")

    assert content.startswith("#!/usr/bin/env bash")
    assert "docker inspect" in content, "must verify container status"
    assert "pg_isready" in content, "must verify database responsiveness"
    assert "postgis" in content.lower(), "must verify the spatial extension"
    assert "set -uo pipefail" in content, "must fail on unbound variables"


def test_healthcheck_script_has_no_crlf_line_endings():
    raw = (REPO_ROOT / "scripts" / "healthcheck.sh").read_bytes()
    assert b"\r\n" not in raw, "shell scripts must use LF so they run in containers/CI"


def test_backend_requirements_cover_deliverable_list():
    requirements = (REPO_ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    required = [
        "fastapi",
        "uvicorn[standard]",
        "sqlalchemy>=2.0",
        "geoalchemy2",
        "alembic",
        "pydantic>=2.0",
        "psycopg2-binary",
        "pytest",
        "httpx",
    ]
    normalized = requirements.lower().replace(" ", "")
    for package in required:
        assert package.lower().replace(" ", "") in normalized, f"missing dependency: {package}"


# ---------------------------------------------------------------------------
# Regression: incident numbering must never collide
# ---------------------------------------------------------------------------
def _create_incident(client, description="Two vehicle collision near Guntur RTC"):
    response = client.post(
        "/api/v1/incidents",
        json={"description": description, "latitude": 16.3067, "longitude": 80.4365},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_incident_numbers_are_unique_and_sequential(client):
    first = _create_incident(client)
    second = _create_incident(client)

    assert first["incident_number"] != second["incident_number"]
    assert first["incident_number"].startswith("INC-")
    first_seq = int(first["incident_number"].rsplit("-", 1)[1])
    second_seq = int(second["incident_number"].rsplit("-", 1)[1])
    assert second_seq == first_seq + 1


def test_incident_numbering_ignores_count_after_external_insert(client, db_session):
    """A gap/foreign row must not cause the next number to be reused."""
    db_session.add(
        Incident(
            id="inc-gap-01",
            incident_number="INC-2026-0007",
            description="Manually imported legacy incident",
            category="FIRE",
            status="ASSESSED",
            severity="LEVEL_3_MODERATE",
            latitude=16.3,
            longitude=80.4,
        )
    )
    db_session.commit()

    created = _create_incident(client)
    year = datetime.now(timezone.utc).year
    assert created["incident_number"] == f"INC-{year}-0008"


# ---------------------------------------------------------------------------
# Regression: unit lifecycle validation and incident consistency
# ---------------------------------------------------------------------------
def _seed_dispatchable(client, db_session):
    unit = EmergencyUnit(
        id="unit-reg-01",
        callsign="AMB-REG-01",
        unit_type="AMBULANCE",
        latitude=16.3067,
        longitude=80.4365,
        status="AVAILABLE",
    )
    incident = Incident(
        id="inc-reg-01",
        incident_number="INC-2026-REG-01",
        description="Cardiac arrest, patient unconscious",
        category="MEDICAL",
        status="RECOMMENDED",
        severity="LEVEL_1_CRITICAL",
        latitude=16.3067,
        longitude=80.4365,
        requires_human_review=False,
    )
    db_session.add_all([unit, incident])
    db_session.commit()


def test_invalid_unit_status_is_rejected(client, db_session):
    _seed_dispatchable(client, db_session)
    response = client.patch(
        "/api/v1/units/unit-reg-01/status",
        json={"status": "TELEPORTED", "dispatcher_id": "DISPATCHER_TEST"},
    )
    assert response.status_code == 400
    assert "Invalid unit status" in response.json()["detail"]

    unit = db_session.query(EmergencyUnit).filter(EmergencyUnit.id == "unit-reg-01").first()
    db_session.refresh(unit)
    assert unit.status == "AVAILABLE"


def test_releasing_dispatched_unit_resolves_incident(client, db_session):
    """DISPATCHED -> AVAILABLE must not leave the incident stuck in DISPATCHED."""
    _seed_dispatchable(client, db_session)

    dispatched = client.post(
        "/api/v1/incidents/inc-reg-01/approve-dispatch",
        json={"unit_id": "unit-reg-01", "dispatcher_id": "DISPATCHER_TEST"},
    )
    assert dispatched.status_code == 200, dispatched.text

    released = client.patch(
        "/api/v1/units/unit-reg-01/status",
        json={"status": "AVAILABLE", "dispatcher_id": "DISPATCHER_TEST"},
    )
    assert released.status_code == 200, released.text
    assert released.json()["unit"]["status"] == "AVAILABLE"
    assert released.json()["incident_status"] == "RESOLVED"

    incident = db_session.query(Incident).filter(Incident.id == "inc-reg-01").first()
    db_session.refresh(incident)
    assert incident.status == "RESOLVED"


def test_recommendations_refused_for_closed_incident(client, db_session):
    _seed_dispatchable(client, db_session)
    incident = db_session.query(Incident).filter(Incident.id == "inc-reg-01").first()
    incident.status = "RESOLVED"
    db_session.commit()

    response = client.post("/api/v1/incidents/inc-reg-01/recommend")
    assert response.status_code == 409
    assert "no longer accepts unit recommendations" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Regression: health endpoint reports real readiness; unknown routes 404
# ---------------------------------------------------------------------------
def test_health_endpoint_reports_database_state(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["database"]["reachable"] is True
    assert payload["database"]["dialect"] in {"sqlite", "postgresql"}


def test_unknown_api_route_returns_404(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Regression: actor width, audit 404, status filter, unit guards, seed idempotency
# ---------------------------------------------------------------------------
def test_sanitize_actor_id_normalizes_and_truncates():
    from backend.app.core.security import ACTOR_MAX_LENGTH, sanitize_actor_id

    assert sanitize_actor_id("  dispatcher_x  ") == "DISPATCHER_X"
    assert sanitize_actor_id(None) == "DISPATCHER_UNKNOWN"
    assert sanitize_actor_id("   ") == "DISPATCHER_UNKNOWN"
    truncated = sanitize_actor_id("z" * 200)
    assert len(truncated) == ACTOR_MAX_LENGTH == 50


def test_oversized_dispatcher_id_is_rejected_before_the_database(client, db_session):
    """The 50-char DB column must be enforced by the schema, not by a 500 at commit."""
    _seed_dispatchable(client, db_session)
    response = client.post(
        "/api/v1/incidents/inc-reg-01/approve-dispatch",
        json={"unit_id": "unit-reg-01", "dispatcher_id": "D" * 80},
    )
    assert response.status_code == 422

    unit = db_session.query(EmergencyUnit).filter(EmergencyUnit.id == "unit-reg-01").first()
    db_session.refresh(unit)
    assert unit.status == "AVAILABLE"


def test_audit_trail_returns_404_for_unknown_incident(client):
    response = client.get("/api/v1/audit/does-not-exist")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_invalid_status_filter_is_rejected(client):
    response = client.get("/api/v1/incidents?status_filter=NOT_A_STATUS")
    assert response.status_code == 400
    assert "Invalid status filter" in response.json()["detail"]

    valid = client.get("/api/v1/incidents?status_filter=assessed")
    assert valid.status_code == 200


def test_busy_unit_status_requires_an_active_assignment(client, db_session):
    unit = EmergencyUnit(
        id="unit-idle-01",
        callsign="AMB-IDLE-01",
        unit_type="AMBULANCE",
        latitude=16.3067,
        longitude=80.4365,
        status="AVAILABLE",
    )
    db_session.add(unit)
    db_session.commit()

    for target in ("DISPATCHED", "ON_SCENE"):
        response = client.patch(
            "/api/v1/units/unit-idle-01/status",
            json={"status": target, "dispatcher_id": "DISPATCHER_TEST"},
        )
        assert response.status_code == 409, response.text
        assert "no active dispatch assignment" in response.json()["detail"]

    db_session.refresh(unit)
    assert unit.status == "AVAILABLE"


def test_seed_units_fills_missing_callsigns_without_duplicates(db_session):
    from backend.app.services.seed_units import SEED_UNITS_DATA, seed_emergency_units

    # Make sure the reference fleet is present, then remove exactly one row.
    seed_emergency_units(db_session)
    target = SEED_UNITS_DATA[0]["callsign"]
    db_session.query(EmergencyUnit).filter(EmergencyUnit.callsign == target).delete()
    db_session.commit()

    assert seed_emergency_units(db_session) == 1
    assert seed_emergency_units(db_session) == 0

    callsigns = [c for (c,) in db_session.query(EmergencyUnit.callsign).all()]
    assert len(callsigns) == len(set(callsigns))
    assert target in callsigns
