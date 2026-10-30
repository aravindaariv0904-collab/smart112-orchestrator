import json
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit

logger = logging.getLogger("smart112.services.matcher")

# Capability matrix for strict resource matching and eligibility filtering
UNIT_CAPABILITIES = {
    "AMBULANCE": {
        "primary_for": {"MEDICAL_EMERGENCY", "TRAFFIC_ACCIDENT", "CARDIAC_ARREST", "OVERDOSE", "MEDICAL"},
        "capabilities": {"ADVANCED_LIFE_SUPPORT", "PATIENT_TRANSPORT", "MEDICAL_TRIAGE"},
        "ineligible_for": {"FIRE_SUPPRESSION", "ARMED_TACTICAL_ENTRY"},
    },
    "FIRE_TRUCK": {
        "primary_for": {"FIRE", "EXPLOSION", "HAZMAT", "RESCUE"},
        "capabilities": {"FIRE_SUPPRESSION", "EXTRICATION", "HAZMAT_CONTAINMENT", "BASIC_LIFE_SUPPORT"},
        "ineligible_for": {"MEDICAL_TRANSPORT"},
    },
    "POLICE_PATROL": {
        "primary_for": {"POLICE", "CRIME", "ASSAULT", "ROBBERY", "WEAPON", "SECURITY"},
        "capabilities": {"LAW_ENFORCEMENT", "TRAFFIC_PERIMETER", "CROWD_CONTROL", "BASIC_FIRST_AID"},
        "ineligible_for": {"FIRE_SUPPRESSION", "ADVANCED_LIFE_SUPPORT_TRANSPORT"},
    },
    "RESCUE_SQUAD": {
        "primary_for": {"RESCUE", "EXTRICATION", "COLLAPSE", "WATER_RESCUE"},
        "capabilities": {"HEAVY_EXTRICATION", "STRUCTURAL_STABILIZATION", "BASIC_LIFE_SUPPORT"},
        "ineligible_for": {"FIRE_SUPPRESSION", "LAW_ENFORCEMENT"},
    },
}


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


def estimate_road_network_metrics(
    direct_km: float, now_utc: Optional[datetime] = None
) -> Tuple[float, float, str, str]:
    """
    Calculates estimated road network distance using an urban/suburban circuity model
    and dynamic transit velocity based on operational time-of-day traffic patterns.
    Returns: (road_km, road_eta_min, traffic_condition, network_type)
    """
    now = now_utc or datetime.now(timezone.utc)
    # Tiered circuity model
    if direct_km <= 10.0:
        circuity = 1.35
        net_type = "URBAN_STREET_GRID_1.35X"
    elif direct_km <= 30.0:
        circuity = 1.25
        net_type = "SUBURBAN_ARTERIAL_1.25X"
    else:
        circuity = 1.18
        net_type = "REGIONAL_HIGHWAY_1.18X"

    road_km = round(direct_km * circuity, 2)

    # Dynamic traffic speed model (IST timezone offset UTC +5:30)
    ist_hour = (now.hour + 5 + (now.minute + 30) // 60) % 24
    if 8 <= ist_hour <= 11 or 17 <= ist_hour <= 20:
        speed_kmh = 32.0
        traffic = "PEAK_HOUR_CONGESTION"
    elif 22 <= ist_hour or ist_hour <= 6:
        speed_kmh = 50.0
        traffic = "NIGHTTIME_FREE_FLOW"
    else:
        speed_kmh = 42.0
        traffic = "STANDARD_DAYTIME_FLOW"

    road_eta = round(max(1.0, (road_km / speed_kmh) * 60.0 + 0.5), 1)
    return road_km, road_eta, traffic, net_type


def is_unit_eligible(
    unit_type: str, category: str, hazards: List[str], casualty_count: int
) -> Tuple[bool, int, str]:
    """
    Evaluates unit operational eligibility and capability priority.
    Returns: (is_eligible, priority_rank [0=highest, 1=secondary, 2=support], rationale)
    """
    u_type = unit_type.upper()
    cat = category.upper()

    # Rule 1: Medical emergencies & Cardiac arrest
    if any(k in cat for k in ("MEDICAL", "CARDIAC", "HEALTH")):
        if u_type == "AMBULANCE":
            return True, 0, "Primary ALS medical transport unit"
        if u_type in ("FIRE_TRUCK", "RESCUE_SQUAD"):
            return True, 1, "First responder BLS medical support"
        # Police not equipped for medical patient care
        return False, 9, "Ineligible: Not certified for medical emergency transport"

    # Rule 2: Fire, explosion, hazmat
    if any(k in cat for k in ("FIRE", "EXPLOSION", "HAZMAT")):
        if u_type == "FIRE_TRUCK":
            return True, 0, "Primary fire suppression and hazmat containment"
        if u_type == "AMBULANCE" and (casualty_count > 0 or "trapped_persons" in hazards):
            return True, 1, "Secondary casualty medical care"
        if u_type == "POLICE_PATROL":
            return True, 2, "Perimeter security and traffic routing"
        return False, 9, "Ineligible: Lacks fire suppression capability"

    # Rule 3: Crime, robbery, assault, weapons
    if any(k in cat for k in ("POLICE", "CRIME", "ASSAULT", "WEAPON", "ROBBERY", "SECURITY")):
        if u_type == "POLICE_PATROL":
            return True, 0, "Primary armed law enforcement unit"
        if u_type == "AMBULANCE" and casualty_count > 0:
            return True, 1, "Tactical medical triage staged behind perimeter"
        return False, 9, "Ineligible: Civilian units barred from active tactical zones"

    # Rule 4: Traffic accidents
    if any(k in cat for k in ("TRAFFIC", "ACCIDENT", "COLLISION")):
        if u_type == "AMBULANCE":
            return True, 0, "Primary vehicular trauma care unit"
        if u_type == "FIRE_TRUCK" and any(h in hazards for h in ("fuel_leak", "fire", "trapped_persons", "pinned")):
            return True, 1, "Secondary extrication and fire hazard mitigation"
        if u_type == "POLICE_PATROL":
            return True, 2, "Traffic diversion and accident investigation"
        return True, 2, "General emergency support"

    # Default general emergency
    return True, 1, "General emergency response"


def match_candidate_units(
    db: Session,
    incident: Incident,
    limit: int = 3,
) -> Dict[str, Any]:
    """
    Identifies, filters, and ranks available emergency units based on:
    - BUG-04: Strict resource capability and eligibility filtering.
    - BUG-03: Road-network routing metrics, freshness timestamp, and traffic conditions.
    - Honest location boundary and unconfirmed coordinates detection.
    - Resource shortage & mutual aid alerting.
    """
    now_utc = datetime.now(timezone.utc)
    freshness_timestamp = now_utc.isoformat()

    # 1. Parse structured assessment data
    assessment = {}
    if incident.assessment_data:
        try:
            assessment = json.loads(incident.assessment_data)
        except Exception:
            assessment = {}

    lat = float(incident.latitude or 0.0)
    lon = float(incident.longitude or 0.0)

    # 2. Honest Location Verification
    # Check for unconfirmed Null Island coordinates (0.0, 0.0)
    if abs(lat) < 0.0001 and abs(lon) < 0.0001:
        logger.warning("Incident %s has unconfirmed (0, 0) coordinates; suppressing spatial ETA.", incident.id)
        return {
            "incident_id": incident.id,
            "candidate_units": [],
            "location_status": "UNCONFIRMED_COORDINATES",
            "resource_deficit": False,
            "freshness_timestamp": freshness_timestamp,
            "rationale": (
                "Incident coordinates are unconfirmed (0, 0). Dispatcher must verify exact "
                "address or scene coordinates before spatial routing can be calculated."
            ),
        }

    # Regional operational boundary check
    dist_from_district_center = haversine_distance_km(
        lat, lon, settings.DEFAULT_LATITUDE, settings.DEFAULT_LONGITUDE
    )
    is_out_of_district = dist_from_district_center > 120.0
    location_status = "OUT_OF_DISTRICT_REGIONAL" if is_out_of_district else "VERIFIED_IN_DISTRICT"

    # 3. Multi-Hazard & Operational Requirements
    category = (incident.category or "").upper()
    hazards = [str(h).lower() for h in assessment.get("hazards", [])]
    casualty_count = assessment.get("casualty_count", 0)

    preferred_type = "AMBULANCE"
    if any(k in category for k in ("FIRE", "EXPLOSION", "HAZMAT")):
        preferred_type = "FIRE_TRUCK"
    elif any(k in category for k in ("POLICE", "CRIME", "ASSAULT", "WEAPON", "ROBBERY", "SECURITY")):
        preferred_type = "POLICE_PATROL"
    elif any(k in category for k in ("TRAFFIC", "ACCIDENT", "COLLISION")):
        preferred_type = "AMBULANCE"
    elif any(k in category for k in ("MEDICAL", "CARDIAC", "HEALTH")):
        preferred_type = "AMBULANCE"

    # 4. Query Available Units
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
            "location_status": location_status,
            "resource_deficit": True,
            "freshness_timestamp": freshness_timestamp,
            "rationale": "No emergency units are currently AVAILABLE. Mutual aid escalation required.",
        }

    # 5. Strict Capability & Eligibility Filtering (BUG-04)
    eligible_units = []
    for unit in available_units:
        eligible, priority, reason = is_unit_eligible(unit.unit_type, category, hazards, casualty_count)
        if eligible:
            eligible_units.append((unit, priority, reason))
        else:
            logger.info("Unit %s (%s) filtered out as ineligible: %s", unit.callsign, unit.unit_type, reason)

    if not eligible_units:
        if available_units:
            logger.warning("No strictly eligible units available for %s; deploying cross-discipline first responders.", category)
            for u in available_units:
                eligible_units.append((u, 3, f"Cross-discipline emergency support ({u.unit_type})"))
        else:
            logger.warning("No available units match the required operational capabilities for %s", category)
            return {
                "incident_id": incident.id,
                "candidate_units": [],
                "location_status": location_status,
                "resource_deficit": True,
                "freshness_timestamp": freshness_timestamp,
                "rationale": (
                    f"RESOURCE DEFICIT ALERT: No units meeting required capabilities ({preferred_type}) are currently eligible. "
                    f"Mutual aid escalation required."
                ),
            }

    # Resource deficit check for preferred type
    has_preferred = any(unit.unit_type == preferred_type for unit, _, _ in eligible_units)
    resource_deficit = not has_preferred

    # 6. PostGIS Spatial Distance Query
    postgis_distances: Dict[str, float] = {}
    bind = db.get_bind()
    is_postgres = bind is not None and bind.dialect.name == "postgresql"
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
            result = db.execute(query, {"lon": lon, "lat": lat}).fetchall()
            for row in result:
                postgis_distances[str(row[0])] = round(float(row[1]), 2)
            logger.info("Calculated unit proximity using native PostGIS ST_Distance.")
        except Exception as e:
            logger.warning("PostGIS spatial query failed (%s); falling back to in-memory Haversine.", e)
            postgis_distances = {}

    # 7. Calculate Proximity, Road Network Distance, and Fresh ETAs (BUG-03)
    candidates = []
    for unit, cap_priority, cap_reason in eligible_units:
        if unit.id in postgis_distances:
            dist_km = postgis_distances[unit.id]
        else:
            dist_km = haversine_distance_km(lat, lon, unit.latitude, unit.longitude)

        # Baseline velocity ETA (keeps exact backward compatibility with test contracts)
        eta_min = calculate_eta_minutes(dist_km, settings.URBAN_SPEED_KMH)

        # Road network routing model with dynamic traffic conditions (BUG-03)
        road_km, road_eta, traffic_cond, net_type = estimate_road_network_metrics(dist_km, now_utc)

        # ETA confidence classification
        if is_out_of_district:
            eta_conf = "REGIONAL_ESTIMATE"
        elif dist_km <= 8.0:
            eta_conf = "HIGH_URBAN_ACCURACY"
        elif dist_km <= 25.0:
            eta_conf = "MODERATE_SUBURBAN"
        else:
            eta_conf = "INTER_CITY_TRANSIT"

        candidates.append({
            "unit_id": unit.id,
            "callsign": unit.callsign,
            "type": unit.unit_type,
            "distance_km": dist_km,
            "road_distance_km": road_km,
            "eta_minutes": eta_min,
            "road_eta_minutes": road_eta,
            "eta_basis": "URBAN_40KMH_LIGHTS_SIRENS",
            "eta_source": net_type,
            "traffic_condition": traffic_cond,
            "eta_confidence": eta_conf,
            "capability_role": cap_reason,
            "status": unit.status,
            "station": unit.station,
            "latitude": unit.latitude,
            "longitude": unit.longitude,
            # Strict sort: capability priority first, then direct distance, then callsign
            "_sort_key": (cap_priority, dist_km, (unit.callsign or "").upper()),
        })

    # 8. Sort and Slice
    candidates.sort(key=lambda x: x["_sort_key"])
    top_candidates = candidates[:limit]

    cleaned_candidates = []
    for c in top_candidates:
        c_copy = dict(c)
        c_copy.pop("_sort_key", None)
        cleaned_candidates.append(c_copy)

    # 9. Formulate Tactical Operational Rationale
    if cleaned_candidates:
        first = cleaned_candidates[0]
        if resource_deficit:
            rationale = (
                f"RESOURCE DEFICIT ALERT: No {preferred_type} currently available. "
                f"Cross-discipline unit {first['callsign']} ({first['type']}) prioritized at {first['distance_km']} km "
                f"(ETA: {first['eta_minutes']} min) for initial scene stabilization. Mutual aid required."
            )
        else:
            secondary_type = None
            if any(k in category for k in ("TRAFFIC", "ACCIDENT", "COLLISION")) and any(h in hazards for h in ("fuel_leak", "fire", "flames", "trapped_persons", "pinned")):
                secondary_type = "FIRE_TRUCK"
            elif any(k in category for k in ("FIRE", "EXPLOSION", "HAZMAT")) and (casualty_count > 0 or "trapped_persons" in hazards):
                secondary_type = "AMBULANCE"
            secondary_note = f" (co-evaluated for {secondary_type} secondary requirement)" if secondary_type else ""
            rationale = (
                f"Unit {first['callsign']} ({first['type']}) prioritized at {first['distance_km']} km "
                f"with an estimated arrival of {first['eta_minutes']} min. "
                f"Selected based on proximity and operational capability for {category or 'EMERGENCY'} scenario{secondary_note}."
            )

        if is_out_of_district:
            rationale += " Note: Incident coordinates exceed primary municipal district boundary."
    else:
        rationale = "No candidate units identified matching incident criteria."

    return {
        "incident_id": incident.id,
        "candidate_units": cleaned_candidates,
        "rationale": rationale,
        "location_status": location_status,
        "resource_deficit": resource_deficit,
        "freshness_timestamp": freshness_timestamp,
    }
