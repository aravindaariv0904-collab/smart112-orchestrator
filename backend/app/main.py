import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# Cross-Origin Resource Sharing (CORS) for Dispatcher Web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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
        "zero_cost_stack": True
    }
