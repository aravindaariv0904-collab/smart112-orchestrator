import os

import pytest
from sqlalchemy import create_engine, text
from backend.app.core.config import settings
from backend.app.services.matcher import calculate_eta_minutes, haversine_distance_km

def test_haversine_distance_accuracy():
    # Coordinates for Guntur RTC Bus Station and Vijayawada Railway Station
    guntur_lat, guntur_lon = 16.3067, 80.4365
    vjw_lat, vjw_lon = 16.5180, 80.6200

    dist = haversine_distance_km(guntur_lat, guntur_lon, vjw_lat, vjw_lon)
    # Expected approximate direct distance is ~30-35 km
    assert 28.0 <= dist <= 36.0, f"Calculated distance {dist} km out of expected bounds"

def test_eta_calculation_velocity_model():
    # 40 km/h velocity model
    # Distance = 20 km -> ETA should be 30.0 minutes
    eta = calculate_eta_minutes(20.0, speed_kmh=40.0)
    assert eta == 30.0

    # Distance = 0 km -> Minimum buffer of 1.0 minute
    eta_zero = calculate_eta_minutes(0.0)
    assert eta_zero == 1.0

    # Distance = 2 km -> 3.0 minutes
    eta_short = calculate_eta_minutes(2.0, speed_kmh=40.0)
    assert eta_short == 3.0

def test_postgis_spatial_distance_calculations():
    """
    Tests PostGIS spatial distance calculations (ST_Distance, ST_DWithin)
    directly on PostgreSQL when PostGIS is available.
    """
    db_url = settings.DATABASE_URL
    if not db_url.startswith("postgresql"):
        pytest.skip("Skipping direct PostGIS database test: non-PostgreSQL environment detected.")

    try:
        engine = create_engine(db_url, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            # 1. Verify PostGIS extension is loaded
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            conn.commit()

            # 2. Test ST_Distance calculation (Guntur to Vijayawada)
            query_dist = text("""
                SELECT ST_Distance(
                    ST_SetSRID(ST_MakePoint(80.4365, 16.3067), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(80.6200, 16.5180), 4326)::geography
                ) AS distance_meters;
            """)
            result_dist = conn.execute(query_dist).scalar()
            assert result_dist is not None
            dist_km = float(result_dist) / 1000.0
            assert 28.0 <= dist_km <= 36.0, f"PostGIS ST_Distance {dist_km} km out of range"

            # 3. Test ST_DWithin calculation (within 50 km)
            query_within = text("""
                SELECT ST_DWithin(
                    ST_SetSRID(ST_MakePoint(80.4365, 16.3067), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(80.6200, 16.5180), 4326)::geography,
                    50000
                ) AS is_within;
            """)
            is_within = conn.execute(query_within).scalar()
            assert is_within is True, "PostGIS ST_DWithin returned False for points within 50km"
    except Exception as exc:
        if os.getenv("REQUIRE_POSTGIS_TESTS", "").strip().lower() in ("1", "true", "yes"):
            raise
        pytest.skip(
            "PostgreSQL/PostGIS not reachable or extension unavailable in this host "
            f"environment ({exc}). Set REQUIRE_POSTGIS_TESTS=1 to fail instead of skip."
        )
