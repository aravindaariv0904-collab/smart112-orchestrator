import logging
import os
from typing import Tuple

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.core.config import settings

logger = logging.getLogger("smart112.database")

Base = declarative_base()

POSTGIS_EXTENSION_SQL = "CREATE EXTENSION IF NOT EXISTS postgis;"


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """SQLite ignores FOREIGN KEY constraints unless the pragma is enabled per connection."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # pragma: no cover - driver hook
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def ensure_postgis(engine: Engine) -> bool:
    """
    Ensure the PostGIS extension is present on a PostgreSQL target.

    Returns True when the extension is available. Never raises: a missing extension is
    logged loudly because the spatial matcher must fall back to geodesic Haversine maths
    instead of silently corrupting recommendations.
    """
    if engine.dialect.name != "postgresql":
        return False

    try:
        with engine.begin() as conn:
            conn.execute(text(POSTGIS_EXTENSION_SQL))
            version = conn.execute(text("SELECT postgis_version()")).scalar()
        logger.info("PostGIS ready (postgis_version=%s).", version)
        return True
    except Exception as exc:  # pragma: no cover - depends on server privileges
        logger.warning(
            "PostGIS extension could not be enabled (%s). Spatial queries will use the "
            "Haversine fallback. Run 'CREATE EXTENSION IF NOT EXISTS postgis;' as a superuser.",
            exc,
        )
        return False


def _create_postgres_engine(db_url: str) -> Engine:
    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=settings.POSTGRES_POOL_SIZE,
        max_overflow=settings.POSTGRES_MAX_OVERFLOW,
        pool_recycle=1800,
        connect_args={"connect_timeout": settings.POSTGRES_CONNECT_TIMEOUT},
        future=True,
    )


def _create_sqlite_engine(db_url: str) -> Engine:
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        future=True,
    )
    _enable_sqlite_foreign_keys(engine)
    return engine


def init_engine() -> Tuple[Engine, bool]:
    """
    Resolve the runtime engine.

    PostgreSQL is always attempted first. If it is unreachable (or FORCE_SQLITE=true is
    set) the service degrades to a local SQLite file so that the dispatch console keeps
    accepting emergencies instead of failing to boot.
    """
    db_url = settings.DATABASE_URL or ""
    use_sqlite = os.getenv("FORCE_SQLITE", "false").strip().lower() in ("true", "1", "yes")

    if not use_sqlite and db_url.startswith("postgresql"):
        probe_engine = None
        try:
            probe_engine = _create_postgres_engine(db_url)
            with probe_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Successfully connected to primary PostgreSQL engine.")
            ensure_postgis(probe_engine)
            return probe_engine, False
        except Exception as exc:
            if probe_engine is not None:
                probe_engine.dispose()
            logger.warning(
                "Could not connect to PostgreSQL (%s). Falling back to local SQLite engine.",
                exc,
            )

    if not use_sqlite and db_url.startswith("sqlite"):
        # Honour an explicitly configured SQLite DSN instead of discarding it.
        engine = _create_sqlite_engine(db_url)
        logger.info("Using configured SQLite database engine (%s).", db_url)
        return engine, True

    sqlite_url = settings.SQLITE_FALLBACK_URL
    engine = _create_sqlite_engine(sqlite_url)
    logger.info("Initialized SQLite database engine fallback (%s).", sqlite_url)
    return engine, True


engine, is_sqlite = init_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Yield a session and guarantee cleanup even when a request handler raises."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
