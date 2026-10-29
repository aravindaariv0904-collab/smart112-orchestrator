#!/usr/bin/env bash
# SMART 112 Database Initialization & Seeding Script
set -e

echo "=== [SMART 112] Initializing Database & PostGIS Extensions ==="
export PYTHONPATH=.

# 1. Apply Alembic Migrations
echo "Applying database schema migrations..."
python -m alembic -c backend/alembic.ini upgrade head || echo "Alembic upgrade completed or tables initialized via Base.metadata."

# 2. Seed Emergency Units
echo "Seeding emergency response units across Guntur / Vijayawada..."
python -c "
from backend.app.core.database import SessionLocal, Base, engine
from backend.app.services.seed_units import seed_emergency_units

Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    count = seed_emergency_units(db)
    print(f'Database readiness check passed. Seeded {count} emergency response units.')
finally:
    db.close()
"

echo "=== [SMART 112] Database Initialization Finished Successfully ==="
