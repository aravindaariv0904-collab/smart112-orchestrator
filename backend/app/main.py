import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from backend.app.core.config import settings
from backend.app.core.database import Base, SessionLocal, engine, ensure_postgis, is_sqlite
from backend.app.services.seed_units import seed_emergency_units
from backend.app.api.incidents import router as incidents_router
from backend.app.api.dispatch import router as dispatch_router
from backend.app.api.audit import router as audit_router
from backend.app.api.audio import router as audio_router

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("smart112.main")

# Reserved first path segments that must never be swallowed by the SPA catch-all.
RESERVED_PATH_PREFIXES = {"api", "health", "docs", "redoc", "openapi.json"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: enable PostGIS (PostgreSQL only), ensure tables exist, seed realistic units.
    if settings.SKIP_STARTUP_HOOKS:
        logger.info("SKIP_STARTUP_HOOKS is set; leaving database provisioning to the caller.")
        yield
        return

    logger.info("Initializing SMART 112 Database schemas (backend=%s)...", engine.dialect.name)
    if not is_sqlite:
        ensure_postgis(engine)

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_emergency_units(db)
    finally:
        db.close()

    logger.info("SMART 112 Platform ready for operational dispatch.")
    yield
    logger.info("SMART 112 Platform shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Authoritative AI-Powered Emergency Response & Dispatch Orchestration Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# Strict Cross-Origin Resource Sharing (CORS)
cors_origins = settings.cors_origins_list
allow_all = cors_origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=not allow_all,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Route Mounts
app.include_router(incidents_router, prefix=f"{settings.API_V1_STR}/incidents", tags=["Incidents"])
app.include_router(dispatch_router, prefix=f"{settings.API_V1_STR}", tags=["Dispatch & Units"])
app.include_router(audit_router, prefix=f"{settings.API_V1_STR}/audit", tags=["Audit Ledger"])
app.include_router(audio_router, prefix=f"{settings.API_V1_STR}/audio", tags=["Audio & Transcription"])


def _probe_database() -> dict:
    """Execute a real readiness probe instead of reporting a hard-coded 'healthy'."""
    info = {
        "dialect": engine.dialect.name,
        "fallback_active": bool(is_sqlite),
    }
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            if engine.dialect.name == "postgresql":
                info["postgis_version"] = conn.execute(text("SELECT postgis_version()")).scalar()
        info["reachable"] = True
    except Exception as exc:  # pragma: no cover - depends on live infrastructure
        info["reachable"] = False
        info["error"] = str(exc)
    return info


@app.get("/health", tags=["Health"])
@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
def health_check():
    database = _probe_database()
    payload = {
        "status": "healthy" if database["reachable"] else "degraded",
        "service": "smart112-orchestrator",
        "ssot_enforced": True,
        "zero_cost_stack": True,
        "environment": settings.ENVIRONMENT,
        "whisper_device": settings.WHISPER_DEVICE,
        "database": database,
    }
    if not database["reachable"]:
        return JSONResponse(status_code=503, content=payload)
    return payload


# Check for pre-built frontend distribution directory (Hugging Face Spaces / Production)
frontend_dist_dirs = [
    os.path.join(os.path.dirname(__file__), "../../../frontend/dist"),
    os.path.join(os.path.dirname(__file__), "../../frontend/dist"),
    os.path.join(os.getcwd(), "frontend/dist"),
    os.path.join(os.getcwd(), "dist"),
]

dist_path = None
for candidate in frontend_dist_dirs:
    norm_candidate = os.path.realpath(candidate)
    if os.path.isdir(norm_candidate) and os.path.isfile(os.path.join(norm_candidate, "index.html")):
        dist_path = norm_candidate
        break

if dist_path:
    logger.info("Mounting static frontend assets from: %s", dist_path)

    assets_dir = os.path.join(dist_path, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Never intercept API, health or documentation traffic.
        first_segment = full_path.split("/", 1)[0].lower()
        if first_segment in RESERVED_PATH_PREFIXES:
            raise HTTPException(status_code=404, detail="Not Found")

        # Resolve inside the distribution root only (blocks ../ path traversal).
        file_target = os.path.realpath(os.path.join(dist_path, full_path))
        if not (file_target == dist_path or file_target.startswith(dist_path + os.sep)):
            raise HTTPException(status_code=404, detail="Not Found")

        if os.path.isfile(file_target):
            return FileResponse(file_target)
        return FileResponse(os.path.join(dist_path, "index.html"))
