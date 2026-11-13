import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def reinit():
    db_file = BASE_DIR / "smart112.db"
    if db_file.exists():
        try:
            os.remove(db_file)
            print("[OK] Removed old smart112.db")
        except Exception as e:
            print(f"[WARN] Could not remove smart112.db directly: {e}")

    from backend.app.core.database import Base, engine, SessionLocal
    from backend.app.models import (
        Incident, EmergencyUnit, DispatchAssignment, AuditLog,
        User, Role, UserSession, Responder,
        Facility, HospitalDepartment, PatientHandover,
        Vehicle, GPSDevice, GPSReading, LocationHistory, Geofence,
        AgentExecution, AgentTrace, Notification, NotificationTemplate
    )
    from backend.app.services.seed_units import seed_emergency_units

    print("[*] Creating all database schemas with updated models...")
    Base.metadata.create_all(bind=engine)
    print("[OK] Schemas created successfully!")

    db = SessionLocal()
    try:
        # 1. Seed 10 Reference Emergency Units
        seed_emergency_units(db)
        print("[OK] Reference emergency fleet seeded.")

        # 2. Seed Default Roles
        roles_data = [
            ("role-admin", "ADMIN", "Full administrative access", "DISPATCH_UNITS,OVERRIDE_TRIAGE,UPDATE_UNIT_STATUS,VIEW_AUDIT,PURGE_INCIDENTS,CREATE_USERS,MANAGE_USERS,MANAGE_FACILITIES,MANAGE_GEOFENCES,MANAGE_NOTIFICATIONS"),
            ("role-sup", "SUPERVISOR", "Incident supervisor", "DISPATCH_UNITS,OVERRIDE_TRIAGE,UPDATE_UNIT_STATUS,VIEW_AUDIT"),
            ("role-dsp", "DISPATCHER", "CAD dispatch operator", "DISPATCH_UNITS,UPDATE_UNIT_STATUS,VIEW_AUDIT"),
            ("role-call", "CALL_TAKER", "Emergency intake operator", "INTAKE_INCIDENTS,VIEW_AUDIT"),
            ("role-res", "RESPONDER", "Field responder & MDT operator", "UPDATE_UNIT_STATUS"),
            ("role-cit", "CITIZEN", "Civilian emergency caller", "INTAKE_INCIDENTS"),
        ]
        for rid, rname, rdesc, rperms in roles_data:
            existing = db.query(Role).filter(Role.name == rname).first()
            if not existing:
                db.add(Role(id=rid, name=rname, description=rdesc, permissions=rperms, is_system_role=True))
        db.commit()
        print("[OK] RBAC Roles seeded.")

        # 3. Seed Reference Hospitals & Facilities
        hospitals = [
            Facility(
                id="fac-guntur-ggh",
                facility_id="FAC-GGH-01",
                name="Guntur Government General Hospital (GGH)",
                facility_type="HOSPITAL",
                subtype="trauma_center",
                address="Collectorate Road, Sambasiva Pet, Guntur, AP 522004",
                latitude=16.3067,
                longitude=80.4365,
                phone="+91 863 222 0112",
                email="emergency@gghguntur.gov.in",
                timezone="Asia/Kolkata",
                has_emergency=True,
                has_emergency_department=True,
                has_icu=True,
                has_trauma_center=True,
                has_operating_theatre=True,
                has_ambulance_bay=True,
                has_blood_bank=True,
                bed_count=850,
                available_beds=64,
                icu_beds_available=14,
                general_beds_available=50,
                status="operational",
                is_active=True,
                operating_hours="24x7 Emergency Services",
                description="Apex tertiary trauma and multi-specialty government emergency facility."
            ),
            Facility(
                id="fac-aiims-mgl",
                facility_id="FAC-AIIMS-01",
                name="AIIMS Mangalagiri Super-Specialty Hospital",
                facility_type="HOSPITAL",
                subtype="trauma_center",
                address="NH-16, Mangalagiri, Guntur District, AP 522503",
                latitude=16.4385,
                longitude=80.5658,
                phone="+91 8645 280112",
                email="cad.dispatch@aiimsmangalagiri.edu.in",
                timezone="Asia/Kolkata",
                has_emergency=True,
                has_emergency_department=True,
                has_icu=True,
                has_trauma_center=True,
                has_operating_theatre=True,
                has_ambulance_bay=True,
                has_blood_bank=True,
                bed_count=960,
                available_beds=112,
                icu_beds_available=28,
                general_beds_available=84,
                status="operational",
                is_active=True,
                operating_hours="24x7 Emergency Services",
                description="National institute with advanced cardiac, neurological, and burn resuscitation units."
            ),
            Facility(
                id="fac-manipal-tpg",
                facility_id="FAC-MANIPAL-01",
                name="Manipal Hospital Tadepalle Bypass",
                facility_type="HOSPITAL",
                subtype="trauma_center",
                address="Tadepalle Bypass, Guntur-Vijayawada Corridor, AP 522501",
                latitude=16.4782,
                longitude=80.6025,
                phone="+91 866 257 0112",
                email="emergency.vja@manipalhospitals.com",
                timezone="Asia/Kolkata",
                has_emergency=True,
                has_emergency_department=True,
                has_icu=True,
                has_trauma_center=True,
                has_operating_theatre=True,
                has_ambulance_bay=True,
                has_blood_bank=True,
                bed_count=450,
                available_beds=38,
                icu_beds_available=8,
                general_beds_available=30,
                status="operational",
                is_active=True,
                operating_hours="24x7 Emergency Services",
                description="Level-1 private emergency center with dedicated cath lab and pediatric intensive care."
            ),
        ]
        for h in hospitals:
            db.add(h)
        db.commit()
        print("[OK] Reference hospitals and emergency facilities seeded.")

    finally:
        db.close()

if __name__ == "__main__":
    reinit()
