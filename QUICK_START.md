# SMART 112 — Quick Start Guide

## 🚨 Emergency Response Intelligence Prototype

A full-stack emergency dispatch orchestration system with AI-powered triage, spatial resource matching, and human-in-the-loop authorization.

## 🎯 Key Features

### For Dispatchers (CAD Operations)
- **Incident Queue**: Real-time list of emergencies with severity indicators
- **GIS Map**: OpenStreetMap visualization with incident/unit markers
- **AI Triage**: Automated extraction of emergency facts with multilingual support
- **Resource Recommendations**: Nearest available units with ETAs
- **Dispatch Authorization**: Human approval gate with RBAC security
- **Audit Trail**: Immutable logging of all actions

### For Citizens (Public Portal)
- **Emergency Reporting**: Submit incidents with description, location, address
- **Interactive Map**: Click to place location pin
- **Quick Presets**: One-click emergency type selection
- **Live Tracking**: Watch incident progress through dispatch lifecycle

### For Responders (MDT)
- **Unit Status**: Acknowledge, arrive, clear workflow
- **Mission Details**: View assigned incident information
- **Field Notes**: Record observations with status updates

## 🚀 Running the Application

### Prerequisites
- Python 3.11+
- Node.js 20+
- npm

### Quick Start (Development)
```bash
# 1. Start backend (Terminal 1)
cd smart112-orchestrator
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# 2. Start frontend (Terminal 2)
cd smart112-orchestrator/frontend
npm run dev
```

Open http://localhost:5173

### Production Build
```bash
cd smart112-orchestrator/frontend
npm run build

cd smart112-orchestrator
uvicorn backend.app.main:app --host 0.0.0.0 --port 7860
```

Open http://localhost:7860

## 🧪 Testing

```bash
# Backend tests (84 tests)
cd smart112-orchestrator
python -m pytest backend/tests/ -v

# Frontend tests (9 tests)
cd smart112-orchestrator/frontend
npm test

# End-to-end simulation
cd smart112-orchestrator
python scripts/run_e2e_simulation.py
```

## 📊 Current Test Status

| Test Suite | Status | Count |
|------------|--------|-------|
| Backend (pytest) | ✅ PASS | 84 passed, 1 skipped |
| Frontend (Vitest) | ✅ PASS | 9 passed |
| E2E Simulation | ✅ PASS | 7 phases |

**Total: 93 tests passing**

## 🔐 Demo Credentials

Dispatcher login (for auth testing):
- Username: `dispatcher_sarah`
- Password: `cad112pass`

## 🗺️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SMART 112 Platform                       │
├─────────────────────────────────────────────────────────────┤
│  Frontend (React + TypeScript + Tailwind)                   │
│  - CAD Operations Center                                    │
│  - Public Portal                                            │
│  - Responder MDT                                            │
│  - Analytics Dashboard                                      │
│  - Audit View                                               │
├─────────────────────────────────────────────────────────────┤
│  Backend (FastAPI + SQLAlchemy + SQLite/PostgreSQL)         │
│  - Incident Management API                                  │
│  - Dispatch & Unit Tracking API                             │
│  - Audit Ledger API                                         │
│  - Authentication & RBAC API                                │
│  - AI Extraction Service                                    │
│  - Spatial Matching Service                                 │
├─────────────────────────────────────────────────────────────┤
│  AI Layer                                                   │
│  - Google Gemini (optional, requires API key)               │
│  - Deterministic NLP Fallback (always available)            │
│  - Multilingual: English, Telugu, Hindi                     │
├─────────────────────────────────────────────────────────────┤
│  Data Layer                                                 │
│  - SQLite (default, zero-config)                           │
│  - PostgreSQL + PostGIS (optional, faster spatial queries) │
│  - Immutable Audit Ledger                                   │
└─────────────────────────────────────────────────────────────┘
```

## 🎨 Design System

- **Primary Background**: Deep navy (#080D1A)
- **Cards/Surfaces**: Slate (#0F172A, #151F32)
- **Critical Alerts**: Emergency red (#E11D48)
- **Warnings**: Amber (#F59E0B)
- **Success/Available**: Emerald (#10B981)
- **Typography**: System sans-serif with monospace for IDs
- **Animations**: Subtle, purposeful, respects reduced-motion

## ⚠️ Limitations

This is a **simulation prototype**. All data is simulated:
- No real emergency services integration
- No live GPS tracking
- No real routing/ETA provider
- No cryptographic audit sealing
- AI uses deterministic fallback (Gemini optional)

**Do not use for real emergencies. Call 112.**

## 📄 Documentation

- `IMPLEMENTATION_COMPLETE.md` - Full implementation report
- `IMPLEMENTATION_LOG.md` - Progress log
- `README.md` - Original project documentation
- `backend/tests/` - Test suites
- `docs/` - System design documents (if available)

## 🤝 Technology Stack

- **Frontend**: React 18, TypeScript 5.6, Vite 5.4, Tailwind CSS 3.4
- **Backend**: FastAPI, SQLAlchemy 2.0, SQLite/PostgreSQL
- **AI**: Google Gemini (optional), Deterministic NLP rules
- **Maps**: Leaflet.js, OpenStreetMap
- **Testing**: pytest, Vitest, Testing Library
- **Auth**: Custom token-based with RBAC

## ✅ Verification Checklist

- [x] Application builds successfully
- [x] All backend tests pass (84/84)
- [x] All frontend tests pass (9/9)
- [x] E2E simulation completes (7/7 phases)
- [x] Incident creation & persistence works
- [x] AI triage extracts facts correctly
- [x] Spatial matching recommends units
- [x] Dispatch authorization enforced
- [x] Unit state machine works correctly
- [x] Audit logging captures all events
- [x] Public portal accepts reports
- [x] Map renders with markers
- [x] Analytics shows real metrics
- [x] RBAC prevents unauthorized dispatch
- [x] Error states handled gracefully
- [x] Loading states implemented
- [x] Empty states provided
- [x] Animations purposeful and restrained

---

**SMART 112** — Authoritative AI-Augmented Emergency Dispatch Orchestrator

Built with ❤️ for emergency response innovation
