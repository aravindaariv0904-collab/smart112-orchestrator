import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.app.models.incident import Incident
from backend.app.services.matcher import haversine_distance_km

logger = logging.getLogger("smart112.services.correlator")


def calculate_duplicate_correlation(
    new_lat: float,
    new_lon: float,
    new_category: str,
    new_hazards: List[str],
    candidate: Incident,
    now_utc: Optional[datetime] = None,
) -> Tuple[float, Dict[str, Any]]:
    """
    Computes a multi-dimensional correlation score between a new emergency report
    and an existing active incident record.

    Dimensions:
    1. Spatial Proximity (45% weight): Haversine distance in meters.
    2. Temporal Proximity (30% weight): Elapsed minutes since initial report.
    3. Semantic Overlap (25% weight): Category compatibility and common hazards.

    Returns:
        (composite_score, correlation_details)
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    # 1. Spatial Score
    dist_km = haversine_distance_km(new_lat, new_lon, candidate.latitude, candidate.longitude)
    dist_m = int(dist_km * 1000)

    if dist_m <= 100:
        spatial_score = 1.0
    elif dist_m <= 500:
        spatial_score = 1.0 - ((dist_m - 100) / 400.0) * 0.4  # 1.0 down to 0.6
    elif dist_m <= 1500:
        spatial_score = max(0.0, 0.6 - ((dist_m - 500) / 1000.0) * 0.6)
    else:
        spatial_score = 0.0

    # 2. Temporal Score
    cand_time = candidate.created_at
    if cand_time:
        if cand_time.tzinfo is None:
            cand_time = cand_time.replace(tzinfo=timezone.utc)
        delta_sec = max(0.0, (now_utc - cand_time).total_seconds())
        delta_min = round(delta_sec / 60.0, 1)
    else:
        delta_min = 0.0

    if delta_min <= 10.0:
        temporal_score = 1.0
    elif delta_min <= 30.0:
        temporal_score = 1.0 - ((delta_min - 10.0) / 20.0) * 0.4  # 1.0 down to 0.6
    elif delta_min <= 60.0:
        temporal_score = max(0.0, 0.6 - ((delta_min - 30.0) / 30.0) * 0.6)
    else:
        temporal_score = 0.0

    # 3. Semantic Category & Hazard Score
    cand_cat = (candidate.category or "").upper()
    new_cat = (new_category or "").upper()

    if cand_cat == new_cat:
        category_score = 1.0
    elif any(k in cand_cat for k in ("ACCIDENT", "COLLISION", "TRAFFIC")) and any(
        k in new_cat for k in ("ACCIDENT", "COLLISION", "TRAFFIC")
    ):
        category_score = 0.9
    elif "GENERAL" in cand_cat or "GENERAL" in new_cat:
        category_score = 0.6
    else:
        category_score = 0.2

    # Hazard overlap
    cand_hazards = set()
    if candidate.assessment_data:
        try:
            import json
            cand_data = json.loads(candidate.assessment_data)
            cand_hazards = set(cand_data.get("hazards", []))
        except Exception:
            pass

    new_h_set = set(new_hazards)
    if new_h_set and cand_hazards:
        jaccard = len(new_h_set & cand_hazards) / len(new_h_set | cand_hazards)
    elif not new_h_set and not cand_hazards:
        jaccard = 0.8
    else:
        jaccard = 0.4

    semantic_score = (0.6 * category_score) + (0.4 * jaccard)

    # Composite weighted correlation
    composite = round(
        (0.45 * spatial_score) + (0.30 * temporal_score) + (0.25 * semantic_score),
        2,
    )

    details = {
        "candidate_id": candidate.id,
        "candidate_incident_number": candidate.incident_number,
        "distance_meters": dist_m,
        "delta_minutes": delta_min,
        "spatial_score": round(spatial_score, 2),
        "temporal_score": round(temporal_score, 2),
        "semantic_score": round(semantic_score, 2),
        "composite_score": composite,
        "is_potential_duplicate": composite >= 0.65 and dist_m <= 600 and delta_min <= 45.0,
        "rationale": (
            f"Correlated {dist_m}m from active incident {candidate.incident_number} "
            f"reported {delta_min} min ago (category: {candidate.category}, match: {int(composite * 100)}%)."
        ),
    }

    return composite, details


def find_incident_duplicates(
    new_lat: float,
    new_lon: float,
    new_category: str,
    new_hazards: List[str],
    active_incidents: List[Incident],
    threshold: float = 0.65,
) -> List[Dict[str, Any]]:
    """
    Scans active incidents and returns all correlated duplicates sorted by highest score.
    """
    now_utc = datetime.now(timezone.utc)
    matches = []

    for cand in active_incidents:
        score, details = calculate_duplicate_correlation(
            new_lat, new_lon, new_category, new_hazards, cand, now_utc
        )
        if details["is_potential_duplicate"] or score >= threshold:
            matches.append(details)

    matches.sort(key=lambda x: x["composite_score"], reverse=True)
    return matches
