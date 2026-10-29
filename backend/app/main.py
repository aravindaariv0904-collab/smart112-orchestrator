import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.core.config import settings
from backend.app.core.database import Base, engine, SessionLocal
from backend.app.services.seed_units import seed_emergency_units
from backend.app.api.incidents import router as incidents_router
from backend.app.api.dispatch import router as dispatch_router
from backend.app.api.audit import router as audit_router
from backend.app.api.audio import router as audio_router

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("smart112.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables exist & seed realistic emergency units
    logger.info("Initializing SMART 112 Database schemas...")
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
    lifespan=lifespan
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

@app.get("/health", tags=["Health"])
@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "smart112-orchestrator",
        "ssot_enforced": True,
        "zero_cost_stack": True,
        "whisper_device": settings.WHISPER_DEVICE
    }

# Check for pre-built frontend distribution directory (Hugging Face Spaces / Production)
frontend_dist_dirs = [
    os.path.join(os.path.dirname(__file__), "../../../frontend/dist"),
    os.path.join(os.path.dirname(__file__), "../../frontend/dist"),
    os.path.join(os.getcwd(), "frontend/dist"),
    os.path.join(os.getcwd(), "dist"),
]

dist_path = None
for candidate in frontend_dist_dirs:
    norm_candidate = os.path.normpath(candidate)
    if os.path.isdir(norm_candidate) and os.path.exists(os.path.join(norm_candidate, "index.html")):
        dist_path = norm_candidate
        break

if dist_path:
    logger.info(f"Mounting static frontend assets from: {dist_path}")
    # Mount assets subfolder if exists
    assets_dir = os.path.join(dist_path, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Do not intercept API or health requests
        if full_path.startswith("api/") or full_path.startswith("health") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            return None
        file_target = os.path.join(dist_path, full_path)
        if os.path.isfile(file_target):
            return FileResponse(file_target)
        return FileResponse(os.path.join(dist_path, "index.html"))
