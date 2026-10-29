import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit

# Setup in-memory SQLite database with StaticPool for single shared memory instance
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Seed one test unit and one incident
    unit = EmergencyUnit(
        id="unit-test-01",
        callsign="AMB-TEST-01",
        unit_type="AMBULANCE",
        latitude=16.3067,
        longitude=80.4365,
        status="AVAILABLE"
    )
    db.add(unit)

    incident = Incident(
        id="inc-test-01",
        incident_number="INC-2026-TEST",
        description="Head-on collision, unconscious patient",
        category="TRAFFIC_ACCIDENT",
        status="RECOMMENDED",
        severity="LEVEL_1_CRITICAL",
        latitude=16.3067,
        longitude=80.4365,
        requires_human_review=True
    )
    db.add(incident)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def test_atomic_unit_dispatch_and_double_booking_prevention():
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
    db = TestingSessionLocal()
    unit = db.query(EmergencyUnit).filter(EmergencyUnit.id == "unit-test-01").first()
    assert unit.status == "DISPATCHED"
    db.close()

    # 3. Second dispatch attempt for the same unit must be blocked (HTTP 409)
    # Create second incident
    db = TestingSessionLocal()
    inc2 = Incident(
        id="inc-test-02",
        incident_number="INC-2026-TEST-2",
        description="Second collision report",
        status="RECOMMENDED",
        severity="LEVEL_2_HIGH",
        latitude=16.3070,
        longitude=80.4370
    )
    db.add(inc2)
    db.commit()
    db.close()

    response2 = client.post(
        "/api/v1/incidents/inc-test-02/approve-dispatch",
        json={
            "unit_id": "unit-test-01",
            "dispatcher_id": "DISPATCHER_SARAH"
        }
    )
    assert response2.status_code == 409
    assert "cannot be dispatched" in response2.json()["detail"]
