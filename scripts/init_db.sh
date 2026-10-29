#!/usr/bin/env bash
# =============================================================================
# SMART 112 - Database initialization & seeding
#
# 1. Enables the PostGIS extension (PostgreSQL targets only).
# 2. Applies Alembic migrations up to head.
# 3. Seeds the realistic Guntur / Vijayawada emergency unit fleet (idempotent).
#
# Usage: ./scripts/init_db.sh
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== [SMART 112] Initializing database & PostGIS extension ==="

# 1. Ensure PostGIS exists before any spatial migration runs.
python - <<'PY'
import os
import sys

# `python -` does not always place the cwd on sys.path (notably on Windows).
sys.path.insert(0, os.getcwd())

from sqlalchemy import text
from backend.app.core.database import engine

if engine.dialect.name == "postgresql":
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        print(f"PostGIS ready: {conn.execute(text('SELECT postgis_version()')).scalar()}")
else:
    print(f"Skipping PostGIS (dialect: {engine.dialect.name}).")
PY

# 2. Apply Alembic migrations. The ini uses %(here)s so the -c path is safe.
echo "Applying database schema migrations..."
python -m alembic -c backend/alembic.ini upgrade head

# 3. Seed emergency units (idempotent: only missing callsigns are inserted).
echo "Seeding emergency response units (Guntur / Vijayawada corridor)..."
python - <<'PY'
import os
import sys

sys.path.insert(0, os.getcwd())

from backend.app.core.database import Base, SessionLocal, engine
from backend.app.services.seed_units import seed_emergency_units

Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    created = seed_emergency_units(db)
    print(f"Seed complete: {created} new unit(s) inserted.")
finally:
    db.close()
PY

echo "=== [SMART 112] Database initialization finished successfully ==="
