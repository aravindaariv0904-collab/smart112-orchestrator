import logging
from sqlalchemy.orm import Session
from backend.app.models.unit import EmergencyUnit

logger = logging.getLogger("smart112.services.seed_units")

# 10 realistic units stationed across Guntur / Vijayawada corridor
SEED_UNITS_DATA = [
    # Ambulances (5)
    {
        "callsign": "AMB-GNT-01",
        "unit_type": "AMBULANCE",
        "latitude": 16.3075,
        "longitude": 80.4372,
        "station": "Guntur Government General Hospital",
        "status": "AVAILABLE"
    },
    {
        "callsign": "AMB-GNT-02",
        "unit_type": "AMBULANCE",
        "latitude": 16.2990,
        "longitude": 80.4420,
        "station": "Guntur RTC Complex Base",
        "status": "AVAILABLE"
    },
    {
        "callsign": "AMB-GNT-03",
        "unit_type": "AMBULANCE",
        "latitude": 16.3150,
        "longitude": 80.4280,
        "station": "Arundelpet Emergency Post",
        "status": "AVAILABLE"
    },
    {
        "callsign": "AMB-VJW-01",
        "unit_type": "AMBULANCE",
        "latitude": 16.5062,
        "longitude": 80.6480,
        "station": "Vijayawada Old City General Hospital",
        "status": "AVAILABLE"
    },
    {
        "callsign": "AMB-VJW-02",
        "unit_type": "AMBULANCE",
        "latitude": 16.5180,
        "longitude": 80.6200,
        "station": "Bhavanipuram Trauma Center",
        "status": "AVAILABLE"
    },

    # Police Patrols (3)
    {
        "callsign": "POL-GNT-01",
        "unit_type": "POLICE_PATROL",
        "latitude": 16.3050,
        "longitude": 80.4350,
        "station": "Kothapet Police Station",
        "status": "AVAILABLE"
    },
    {
        "callsign": "POL-GNT-02",
        "unit_type": "POLICE_PATROL",
        "latitude": 16.3200,
        "longitude": 80.4500,
        "station": "Pattabhipuram Precinct",
        "status": "AVAILABLE"
    },
    {
        "callsign": "POL-VJW-01",
        "unit_type": "POLICE_PATROL",
        "latitude": 16.5100,
        "longitude": 80.6350,
        "station": "Governorpet Traffic Precinct",
        "status": "AVAILABLE"
    },

    # Fire Response Units (2)
    {
        "callsign": "FIRE-GNT-01",
        "unit_type": "FIRE_TRUCK",
        "latitude": 16.3020,
        "longitude": 80.4310,
        "station": "Guntur Central Fire Station",
        "status": "AVAILABLE"
    },
    {
        "callsign": "FIRE-VJW-01",
        "unit_type": "FIRE_TRUCK",
        "latitude": 16.5120,
        "longitude": 80.6280,
        "station": "Vijayawada City Fire Station",
        "status": "AVAILABLE"
    }
]

def seed_emergency_units(db: Session) -> int:
    """
    Seeds initial realistic emergency response units into the database if empty.
    Returns count of newly seeded units.
    """
    existing_count = db.query(EmergencyUnit).count()
    if existing_count > 0:
        logger.info(f"Database already contains {existing_count} emergency units. Skipping seed.")
        return 0

    created = 0
    for unit_dict in SEED_UNITS_DATA:
        unit = EmergencyUnit(
            callsign=unit_dict["callsign"],
            unit_type=unit_dict["unit_type"],
            latitude=unit_dict["latitude"],
            longitude=unit_dict["longitude"],
            station=unit_dict["station"],
            status=unit_dict["status"]
        )
        db.add(unit)
        created += 1

    db.commit()
    logger.info(f"Successfully seeded {created} emergency response units.")
    return created
