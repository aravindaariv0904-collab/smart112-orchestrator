"""
Spatial calculation utilities for SMART 112.
"""

from backend.app.services.matcher import haversine_distance_km

# Expose haversine_distance alias
haversine_distance = haversine_distance_km
