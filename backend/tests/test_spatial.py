import pytest
from backend.app.services.matcher import haversine_distance_km, calculate_eta_minutes

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
