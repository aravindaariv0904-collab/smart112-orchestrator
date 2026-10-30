import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.app.models.incident import Incident
from backend.app.models.unit import EmergencyUnit
from backend.app.services.matcher import haversine_distance_km


def calculate_bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates compass heading/bearing in degrees (0-360) between two GPS points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)

    theta = math.atan2(y, x)
    bearing = (math.degrees(theta) + 360.0) % 360.0
    return round(bearing, 1)


def generate_interpolated_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    num_waypoints: int = 5,
) -> List[Dict[str, float]]:
    """
    Generates intermediate waypoints along a road corridor between unit and incident.
    """
    waypoints = []
    for i in range(num_waypoints + 1):
        fraction = i / float(num_waypoints)
        # Slight realistic street-grid jitter
        jitter_lat = 0.0001 * math.sin(fraction * math.pi * 3) if 0 < fraction < 1 else 0.0
        jitter_lon = 0.0001 * math.cos(fraction * math.pi * 3) if 0 < fraction < 1 else 0.0

        w_lat = start_lat + fraction * (end_lat - start_lat) + jitter_lat
        w_lon = start_lon + fraction * (end_lon - start_lon) + jitter_lon
        waypoints.append({
            "step": i,
            "latitude": round(w_lat, 6),
            "longitude": round(w_lon, 6),
            "fraction": round(fraction, 2),
        })
    return waypoints


def compute_unit_telemetry(
    unit: EmergencyUnit,
    incident: Optional[Incident] = None,
) -> Dict[str, Any]:
    """
    Computes real-time telemetry state for a dispatched or available unit.
    Mandatory Transparency: Clearly identifies simulated vs live GPS data (BUG-12).
    """
    now_utc = datetime.now(timezone.utc).isoformat()

    if not incident or unit.status not in ("DISPATCHED", "ON_SCENE"):
        return {
            "unit_id": unit.id,
            "callsign": unit.callsign,
            "unit_type": unit.unit_type,
            "status": unit.status,
            "latitude": unit.latitude,
            "longitude": unit.longitude,
            "heading_degrees": 0.0,
            "speed_kmh": 0.0,
            "is_simulated": True,
            "telemetry_source": "STATIC_STATION_CAD_COORDINATES",
            "last_ping_utc": now_utc,
            "route_waypoints": [],
            "distance_to_target_km": 0.0,
            "estimated_seconds_remaining": 0,
        }

    dist_km = haversine_distance_km(unit.latitude, unit.longitude, incident.latitude, incident.longitude)
    bearing = calculate_bearing_degrees(unit.latitude, unit.longitude, incident.latitude, incident.longitude)
    speed_kmh = 38.5 if unit.status == "DISPATCHED" else 0.0
    seconds_remaining = int((dist_km / max(1.0, speed_kmh)) * 3600) if speed_kmh > 0 else 0

    waypoints = generate_interpolated_route(
        unit.latitude, unit.longitude, incident.latitude, incident.longitude, num_waypoints=4
    )

    return {
        "unit_id": unit.id,
        "callsign": unit.callsign,
        "unit_type": unit.unit_type,
        "status": unit.status,
        "assigned_incident_id": incident.id,
        "assigned_incident_number": incident.incident_number,
        "latitude": unit.latitude,
        "longitude": unit.longitude,
        "heading_degrees": bearing,
        "speed_kmh": speed_kmh,
        "is_simulated": True,
        "telemetry_source": "CAD_SIMULATED_DEAD_RECKONING",
        "last_ping_utc": now_utc,
        "distance_to_target_km": round(dist_km, 2),
        "estimated_seconds_remaining": seconds_remaining,
        "route_waypoints": waypoints,
    }
