import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

logger = logging.getLogger("smart112.database")

Base = declarative_base()

def init_engine():
    db_url = settings.DATABASE_URL
    # Check if we should force or fallback to SQLite
    use_sqlite = os.getenv("FORCE_SQLITE", "false").lower() in ("true", "1")
    
    if not use_sqlite and db_url.startswith("postgresql"):
        try:
            # Test PostgreSQL connection with a short timeout
            test_engine = create_engine(
                db_url,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 2}
            )
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Successfully connected to primary PostgreSQL engine.")
            return test_engine, False
        except Exception as e:
            logger.warning(
                f"Could not connect to PostgreSQL ({e}). Falling back to local SQLite engine."
            )
            
    # Fallback to local SQLite
    sqlite_url = settings.SQLITE_FALLBACK_URL
    engine = create_engine(
        sqlite_url, 
        connect_args={"check_same_thread": False}
    )
    logger.info("Initialized SQLite database engine fallback.")
    return engine, True

engine, is_sqlite = init_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
