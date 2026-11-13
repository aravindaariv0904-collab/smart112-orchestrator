import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# The suite owns its in-memory schema; never run the application's startup
# provisioning against the configured (possibly live) database.
os.environ.setdefault("SMART112_SKIP_STARTUP_HOOKS", "true")

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.unit import EmergencyUnit
from backend.app.models.user import User, Role, Responder
from backend.app.models.dispatch import DispatchAssignment
from backend.app.models.incident import Incident

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="session", autouse=True)
def init_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def db_session():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    # Pre-seed basic test data if missing
    if session.query(EmergencyUnit).count() == 0:
        # Create roles first
        dispatcher_role = Role(
            id="role-dispatcher",
            name="DISPATCHER",
            permissions="DISPATCH_UNITS,UPDATE_UNIT_STATUS,VIEW_AUDIT",
            is_system_role=True
        )
        supervisor_role = Role(
            id="role-supervisor",
            name="SUPERVISOR",
            permissions="DISPATCH_UNITS,OVERRIDE_TRIAGE,UPDATE_UNIT_STATUS,VIEW_AUDIT",
            is_system_role=True
        )
        admin_role = Role(
            id="role-admin",
            name="ADMIN",
            permissions="DISPATCH_UNITS,OVERRIDE_TRIAGE,UPDATE_UNIT_STATUS,VIEW_AUDIT,PURGE_INCIDENTS",
            is_system_role=True
        )
        session.add_all([dispatcher_role, supervisor_role, admin_role])
        session.flush()
        
        # Create users
        dispatcher_user = User(
            id="user-dispatcher-01",
            username="dispatcher_sarah",
            email="sarah@smart112.test",
            role_id="role-dispatcher",
            is_active=True,
            is_verified=True
        )
        dispatcher_user.set_password("cad112pass")
        session.add(dispatcher_user)
        
        supervisor_user = User(
            id="user-supervisor-01",
            username="supervisor_kumar",
            email="kumar@smart112.test",
            role_id="role-supervisor",
            is_active=True,
            is_verified=True
        )
        supervisor_user.set_password("cad112pass")
        session.add(supervisor_user)
        
        admin_user = User(
            id="user-admin-01",
            username="commissioner_lead",
            email="lead@smart112.test",
            role_id="role-admin",
            is_active=True,
            is_verified=True
        )
        admin_user.set_password("cad112pass")
        session.add(admin_user)
        session.flush()
        
        # Create emergency units
        unit = EmergencyUnit(
            id="unit-test-01",
            callsign="AMB-TEST-01",
            unit_type="AMBULANCE",
            latitude=16.3067,
            longitude=80.4365,
            status="AVAILABLE"
        )
        session.add(unit)
        session.flush()
        
        # Create responder profile for dispatcher
        responder = Responder(
            id="responder-test-01",
            user_id="user-dispatcher-01",
            callsign="DISPATCHER_SARAH",
            full_name="Sarah Dispatcher",
            unit_id="unit-test-01",
            is_available=True
        )
        session.add(responder)
        
        session.commit()

    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

