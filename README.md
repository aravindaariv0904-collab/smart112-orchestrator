---
title: SMART 112 Emergency Intelligence
emoji: 🚨
colorFrom: red
colorTo: blue
sdk: docker
app_port: 7860
---

# SMART 112: Authoritative AI-Augmented Emergency Dispatch Orchestrator

[![CI Pipeline](https://github.com/smart112/smart112-orchestrator/actions/workflows/ci.yml/badge.svg)](https://github.com/smart112/smart112-orchestrator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-brightgreen.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![React: 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![Zero-Cost Stack](https://img.shields.io/badge/Zero--Cost-PostGIS%20%2B%20Gemini%20Free%20%2B%20OSM-success.svg)](docs/SYSTEM_DESIGN.md)

**SMART 112** is an enterprise-grade, mission-critical public safety orchestration engine designed to modernize Public Safety Answering Points (PSAPs). Built with **zero marginal recurring software licensing cost**, sub-second fail-safe guarantees, and absolute **Backend Single Source of Truth (SSOT)** supremacy.

---

## 🏛️ System Architecture & Core Pillars

```
+-----------------------------------------------------------------------------------+
|                               SMART 112 ARCHITECTURE                              |
+-----------------------------------------------------------------------------------+
|  1. Single Source of Truth (SSOT)                                                 |
|     - All state transitions & severity logic enforced exclusively by Backend API. |
|     - Zero client-side triage or autonomous auto-dispatch.                        |
|     - Strict atomic row locking to prevent emergency unit double-booking.         |
+-----------------------------------------------------------------------------------+
|  2. Zero-Cost Infrastructure Rule                                                 |
|     - Google Gemini API free tier with non-blocking 3.0s timeout & caching.        |
|     - Local PostgreSQL + PostGIS spatial calculations (ST_Distance, ST_DWithin).   |
|     - OpenStreetMap (OSM) local/open tiles rendered via Leaflet.js engine.        |
+-----------------------------------------------------------------------------------+
|  3. Fail-Safe Resilience & Non-Blocking Fallback                                  |
|     - High-fidelity deterministic NLP rule classifier fallback upon AI timeout.  |
|     - Requires Human Review protocol whenever uncertainty signals emerge.        |
|     - Immutable, append-only chronological Audit Ledger for complete governance.  |
+-----------------------------------------------------------------------------------+
```

Detailed technical architecture and system specifications are documented in:
- [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md): Comprehensive System Design Document with Mermaid diagrams, ER schemas, and failure modes.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): Master System Architecture & State Machine Specification.

---

## 🛠️ Tech Stack & Frameworks

- **Backend Framework**: Python 3.11+, FastAPI, Starlette, Uvicorn (ASGI)
- **Database & Spatial**: PostgreSQL 16 with PostGIS 3.4 (`ST_Distance`, `ST_DWithin`, GIST indexing) with automatic SQLite + Haversine fallback
- **ORM & Migrations**: SQLAlchemy 2.0, Alembic
- **Validation & Settings**: Pydantic v2, Pydantic Settings
- **AI & Speech Triage**: Google Gemini 2.5/2.0 Flash (`google-genai`), `faster-whisper`, Deterministic Rule Engine
- **Frontend Framework**: React 18, TypeScript 5.6, Vite 5.4, Tailwind CSS 3.4, Lucide React
- **Cartography**: Leaflet.js, OpenStreetMap (OSM) raster tiles
- **Testing & Tooling**: Pytest, Vitest, Testing Library, JSDOM, Ruff

---

## 🚦 Incident State Machine Lifecycle

```mermaid
stateDiagram-v2
    [*] --> REPORTED : Citizen Call / Audio Stream Ingested
    
    REPORTED --> ASSESSED : AI NLU Extraction / Gemini Free Tier
    REPORTED --> ASSESSED : AI Timeout / Heuristic Fallback (requires_human_review=true)
    
    ASSESSED --> RECOMMENDED : Spatial PostGIS Proximity Match
    
    RECOMMENDED --> DISPATCHED : Human Dispatcher Confirms Assignment (Atomic Lock)
    
    DISPATCHED --> ON_SCENE : Unit MDT Confirms Arrival at Coordinates
    
    ON_SCENE --> RESOLVED : Incident Stabilized & Sign-off Completed
    
    REPORTED --> CANCELLED : False Alarm / Duplicate Ingest
    ASSESSED --> CANCELLED : Dispatcher Rejection
    RECOMMENDED --> CANCELLED : Caller Stood Down
    DISPATCHED --> CANCELLED : False Call On-Route
```

---

## ⚙️ Environment Variables

The application is configured using environment variables loaded via `.env` (validated by Pydantic v2 `BaseSettings`).

| Variable | Description | Default Value | Required |
| :--- | :--- | :--- | :---: |
| `POSTGRES_USER` | PostgreSQL superuser username | `postgres` | No |
| `POSTGRES_PASSWORD` | PostgreSQL superuser password | `postgres` | No |
| `POSTGRES_DB` | Primary database name | `smart112` | No |
| `POSTGRES_HOST` | Database host address | `localhost` | No |
| `POSTGRES_PORT` | Database connection port | `5432` | No |
| `DATABASE_URL` | Full SQLAlchemy DSN connection string | `postgresql://postgres:postgres@localhost:5432/smart112` | No |
| `SMART112_DATABASE_URL` | Project-scoped DSN override (highest priority) | `None` | No |
| `SQLITE_FALLBACK_URL` | SQLite file DSN fallback if PostgreSQL is offline | `sqlite:///./smart112.db` | No |
| `GEMINI_API_KEY` | Google Gemini API key for real-time emergency NLU | `""` (runs deterministic NLP fallback when empty) | No |
| `WHISPER_DEVICE` | Hardware accelerator for faster-whisper transcription (`cuda` or `cpu`) | `cuda` | No |
| `CORS_ORIGINS` | Permitted cross-origin origins (comma-separated) | `http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173` | No |
| `URBAN_SPEED_KMH` | Average urban speed in km/h used for velocity ETA modeling | `40.0` | No |
| `DEFAULT_LATITUDE` | Regional operational center latitude (Guntur, AP) | `16.3067` | No |
| `DEFAULT_LONGITUDE` | Regional operational center longitude (Guntur, AP) | `80.4365` | No |
| `MAX_AUDIO_UPLOAD_BYTES`| Maximum permitted emergency audio upload size in bytes (15 MB) | `15728640` | No |
| `ENABLE_DESTRUCTIVE_ENDPOINTS` | Allows `/purge-all` reset endpoint in development/testing | `True` (refused in production) | No |
| `ENVIRONMENT` | Runtime deployment environment (`development`, `staging`, `production`) | `development` | No |

---

## 🚀 Quickstart & Local Setup

### 1. Prerequisites
- **Python**: 3.11 or higher
- **Node.js**: 20.x or higher & npm
- **Database**: PostgreSQL 16+ with PostGIS 3.4 extension (or Docker, or automatic local SQLite fallback)

### 2. Configure Environment
```bash
cp .env.example .env
```

### 3. Start Database (Docker Compose)
```bash
# Starts PostgreSQL with PostGIS extension:
docker compose up -d postgres
```

### 4. Apply Database Migrations
```bash
alembic upgrade head
```

### 5. Install Dependencies & Build Frontend
```bash
# In frontend directory:
cd frontend
npm install
npm run build
cd ..
```

### 6. Run Application Server
```bash
# Run FastAPI production server (serves API & static SPA assets):
uvicorn backend.app.main:app --host 0.0.0.0 --port 7860
```
Open your browser to `http://localhost:7860` to access the live SMART 112 Dispatch Operations Command Center.

For frontend hot-reload development:
```bash
# Terminal 1 (Backend):
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 (Frontend Dev Server):
cd frontend && npm run dev
```

---

## 🧪 Verification & Automated Testing

### Backend Unit & Integration Tests (54 Tests)
```bash
# Set PYTHONPATH and execute pytest suite:
PYTHONPATH=. pytest backend/tests/ -v
```

### Fixture-Driven Sample Data Tests
```bash
PYTHONPATH=. pytest backend/tests/test_sample_fixtures.py -v
```

### Frontend Component Tests (Vitest)
```bash
cd frontend && npm test
```

### End-to-End Simulation Script
```bash
# In-process autonomous lifecycle simulation:
python scripts/run_e2e_simulation.py
```

### Live HTTP Verification (10 Master Scenarios)
```bash
# Against running server (http://127.0.0.1:8000 or http://127.0.0.1:7860):
python scripts/verify_e2e.py
```

---

## 📦 Sample Data & Payloads

Realistic mock data payloads and fixtures are stored in [`sample_data/`](sample_data/):
- `sample_data/sample_incidents.json`: Canonical emergency incidents across collision, commercial fire, cardiac arrest, missing information, and duplicate reports.
- `sample_data/sample_units.json`: Emergency units (Ambulance, Fire, Police) positioned across Guntur and Vijayawada.
- `sample_data/sample_dispatch_orders.json`: Authorized and unauthorized dispatch approval payloads.
- `sample_data/sample_triage_assessments.json`: Nominal Gemini responses, timeout fallbacks, and uncertainty payloads.

---

## 🔒 Security Hardening & AppSec Audits

1. **Secret & Key Isolation**:
   - Zero hardcoded API keys or database credentials in source tree.
   - Pydantic v2 `BaseSettings` (`backend/app/core/config.py`) loads all configuration securely from environment variables.
2. **API & Input Hardening**:
   - Pydantic schemas sanitize all inputs, stripping malicious HTML tags, null bytes, and script injection vectors.
   - Strict CORS policy restricting access to authorized frontend origins.
   - `/api/v1/audio/transcribe` enforces a 15 MB payload ceiling and verifies allowed audio container magic headers (`audio/wav`, `audio/mpeg`, `audio/mp3`, `audio/ogg`).
3. **Immutable Audit Ledger**:
   - `AuditLog` records cannot be updated or deleted via any REST API endpoint (prohibits PUT, PATCH, DELETE operations).
4. **Row-Level Concurrency Guard**:
   - Exclusive `with_for_update()` locking on unit dispatch orders eliminates race conditions and vehicle double-booking.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
