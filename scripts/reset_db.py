#!/usr/bin/env python3
"""
SMART 112 operator utility: reset the operational dataset.

Deletes incidents, dispatch assignments and audit records, then returns every
emergency unit to AVAILABLE. Works against whatever database the application is
configured for (PostgreSQL/PostGIS or the SQLite fallback).

Usage:
    python scripts/reset_db.py --yes            # interactive confirmation skipped
    python scripts/reset_db.py                  # prompts before deleting
    python scripts/reset_db.py --yes --quiet

Safety:
    * Refuses to run when ENVIRONMENT=production or
      ENABLE_DESTRUCTIVE_ENDPOINTS=false.
    * Deletes children before parents so foreign keys never block the reset.
    * Rolls back atomically on any failure.
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure the repository root is importable when run as a plain script.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete, func, select, update  # noqa: E402

from backend.app.core.config import settings  # noqa: E402
from backend.app.core.database import SessionLocal, engine  # noqa: E402
from backend.app.models.audit import AuditLog  # noqa: E402
from backend.app.models.dispatch import DispatchAssignment  # noqa: E402
from backend.app.models.incident import Incident  # noqa: E402
from backend.app.models.unit import EmergencyUnit  # noqa: E402


def _guard_environment() -> None:
    if settings.is_production or not settings.ENABLE_DESTRUCTIVE_ENDPOINTS:
        print(
            "REFUSED: destructive reset is disabled "
            f"(ENVIRONMENT={settings.ENVIRONMENT}, "
            f"ENABLE_DESTRUCTIVE_ENDPOINTS={settings.ENABLE_DESTRUCTIVE_ENDPOINTS}).",
            file=sys.stderr,
        )
        raise SystemExit(2)


def reset_database(assume_yes: bool = False, quiet: bool = False) -> dict:
    _guard_environment()

    target = engine.url.render_as_string(hide_password=True)
    print(f"Target database: {target} (dialect: {engine.dialect.name})")

    if not assume_yes:
        answer = input("This deletes ALL incidents, dispatches and audit records. Continue? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Aborted. Nothing was changed.")
            raise SystemExit(1)

    session = SessionLocal()
    try:
        # Children before parents: dispatch_assignments -> incidents -> audit_logs.
        deleted_dispatches = session.execute(delete(DispatchAssignment)).rowcount or 0
        deleted_incidents = session.execute(delete(Incident)).rowcount or 0
        deleted_audits = session.execute(delete(AuditLog)).rowcount or 0
        session.execute(update(EmergencyUnit).values(status="AVAILABLE"))
        session.commit()

        incident_count = session.execute(select(func.count()).select_from(Incident)).scalar_one()
        available_units = session.execute(
            select(func.count())
            .select_from(EmergencyUnit)
            .where(EmergencyUnit.status == "AVAILABLE")
        ).scalar_one()
        total_units = session.execute(
            select(func.count()).select_from(EmergencyUnit)
        ).scalar_one()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    summary = {
        "deleted_dispatches": deleted_dispatches,
        "deleted_incidents": deleted_incidents,
        "deleted_audit_logs": deleted_audits,
        "remaining_incidents": incident_count,
        "available_units": available_units,
        "total_units": total_units,
    }

    if not quiet:
        print(
            "Reset complete: "
            f"{deleted_dispatches} dispatch(es), {deleted_incidents} incident(s), "
            f"{deleted_audits} audit record(s) removed; "
            f"{available_units}/{total_units} units AVAILABLE."
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reset the SMART 112 operational dataset.")
    parser.add_argument("--yes", "-y", action="store_true", help="skip the confirmation prompt")
    parser.add_argument("--quiet", "-q", action="store_true", help="only print errors")
    args = parser.parse_args(argv)

    try:
        reset_database(assume_yes=args.yes, quiet=args.quiet)
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:  # pragma: no cover - operator-facing failure path
        print(f"Reset failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
