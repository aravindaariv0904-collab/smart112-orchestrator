import math
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.core.config import settings
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit

logger = logging.getLogger("smart112.services.matcher")

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth (in km)."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)

def calculate_eta_minutes(distance_km: float, speed_kmh: float = 40.0) -> float:
    """
    Deterministic urban emergency response velocity model.
    Standard average transit velocity: 40 km/h under active lights/sirens.
    """
    if distance_km <= 0:
        return 1.0
    minutes = (distance_km / speed_kmh) * 60.0
    # Minimum 1 minute dispatch preparation/rollout buffer
    return round(max(1.0, minutes), 1)

def match_candidate_units(
    db: Session,
    incident: Incident,
    limit: int = 3
) -> Dict[str, Any]:
    """
    Identifies and ranks top available emergency units based on spatial proximity,
    incident category requirements, and deterministic ETA modeling.
    Uses PostGIS spatial calculation when available; falls back to geodesic Haversine.
    """
    # 1. Determine preferred unit type based on incident category/assessment
    category = (incident.category or "").upper()
    preferred_type = "AMBULANCE"
    if "FIRE" in category or "EXPLOSION" in category or "HAZMAT" in category:
        preferred_type = "FIRE_TRUCK"
    elif "POLICE" in category or "CRIME" in category or "ASSAULT" in category or "WEAPON" in category:
        preferred_type = "POLICE_PATROL"
    elif "TRAFFIC" in category or "ACCIDENT" in category or "COLLISION" in category:
        preferred_type = "AMBULANCE"

    # 2. Query available units from the database
    available_units = (
        db.query(EmergencyUnit)
        .filter(EmergencyUnit.status == "AVAILABLE")
        .all()
    )

    if not available_units:
        logger.warning("No units currently marked AVAILABLE in system.")
        return {
            "incident_id": incident.id,
            "candidate_units": [],
            "rationale": "No emergency units are currently AVAILABLE. Mutual aid escalation required."
        }

    # 3. Check for PostGIS spatial distance capability
    postgis_distances: Dict[str, float] = {}
    is_postgres = db.bind and db.bind.dialect.name == "postgresql"
    if is_postgres:
        try:
            query = text("""
                SELECT id, ST_Distance(
                    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) / 1000.0 AS dist_km
                FROM emergency_units
                WHERE status = 'AVAILABLE'
            """)
            result = db.execute(query, {"lon": incident.longitude, "lat": incident.latitude}).fetchall()
            for row in result:
                postgis_distances[str(row[0])] = round(float(row[1]), 2)
            logger.info("Calculated unit proximity using native PostGIS ST_Distance.")
        except Exception as e:
            logger.warning(f"PostGIS spatial query failed ({e}); falling back to in-memory Haversine.")
            postgis_distances = {}

    # 4. Calculate spatial distances and ETAs
    candidates = []
    for unit in available_units:
        if unit.id in postgis_distances:
            dist_km = postgis_distances[unit.id]
        else:
            dist_km = haversine_distance_km(
                incident.latitude, incident.longitude,
                unit.latitude, unit.longitude
            )
        eta_min = calculate_eta_minutes(dist_km, settings.URBAN_SPEED_KMH)
        
        # Priority boost for matching preferred unit type
        type_priority = 0 if unit.unit_type == preferred_type else 1
        
        candidates.append({
            "unit_id": unit.id,
            "callsign": unit.callsign,
            "type": unit.unit_type,
            "distance_km": dist_km,
            "eta_minutes": eta_min,
            "status": unit.status,
            "station": unit.station,
            "latitude": unit.latitude,
            "longitude": unit.longitude,
            "_sort_key": (type_priority, dist_km)
        })

    # 5. Sort primarily by capability match, then shortest spatial distance
    candidates.sort(key=lambda x: x["_sort_key"])
    top_candidates = candidates[:limit]

    # Clean internal sort keys
    cleaned_candidates = []
    for c in top_candidates:
        c_copy = dict(c)
        c_copy.pop("_sort_key", None)
        cleaned_candidates.append(c_copy)

    # 6. Formulate tactical rationale
    if cleaned_candidates:
        first = cleaned_candidates[0]
        rationale = (
            f"Unit {first['callsign']} ({first['type']}) prioritized at {first['distance_km']} km "
            f"with an estimated arrival of {first['eta_minutes']} min. "
            f"Selected based on proximity and operational capability for {category or 'EMERGENCY'} scenario."
        )
    else:
        rationale = "No candidate units identified matching incident criteria."

    return {
        "incident_id": incident.id,
        "candidate_units": cleaned_candidates,
        "rationale": rationale
    }
