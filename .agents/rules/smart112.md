# SMART 112: Master System Operational Rules & Guardrails

## 1. Single Source of Truth (SSOT)
- **Backend Supremacy**: The backend API (`smart112-backend`) is the definitive, authoritative source of truth for all incident lifecycles, states, evaluations, and telemetry.
- **No Client-Side Authority**:
  - Web clients, mobile MDTs (Mobile Data Terminals), and call-taker interfaces **MUST NEVER** calculate emergency severity levels locally.
  - Clients **MUST NEVER** autonomously execute dispatch actions or alter lifecycle states without explicit, authenticated backend validation and confirmation.
  - All status transitions, triage calculations, unit distance validations, and dispatch decisions originate from or are validated by the backend state machine.
- **Human-in-the-Loop Authority**:
  - AI triage and recommendation systems generate decision-support candidates.
  - Final dispatch confirmation requires human dispatcher approval unless explicit policy-governed emergency escalation rules are triggered under audit logging.

---

## 2. Zero-Cost Infrastructure Rule
The system is engineered for maximum resilience, community accessibility, and zero software licensing / third-party API recurring costs:
- **AI / LLM Ingestion & Triage**:
  - Utilizes Google Gemini API free tier (e.g., Gemini 2.0 Flash / Gemini 1.5 Flash) via authorized API keys with strict rate-limit backoff and caching.
  - No paid proprietary LLM gateways or enterprise metering layers required for standard operations.
- **Geodata & Spatial Storage**:
  - Powered by local **PostgreSQL + PostGIS** extensions running on local or containerized infrastructure.
  - Spatial indexes (`GIST`), geodesic distance calculations (`ST_DistanceSphere`), and proximity searches execute directly inside PostGIS with zero external query fees.
- **Cartography & Visualization**:
  - Local **OpenStreetMap (OSM)** raster/vector tile servers or free public OSM tile endpoints.
  - Browser rendering via **Leaflet.js** or MapLibre GL open-source engines.
  - Prohibits hard dependencies on paid mapping platforms (such as Google Maps Platform, Mapbox, or Here) for primary dispatch routing and map views.

---

## 3. Fail-Safe & Graceful Degradation Protocol
Emergency 112 operations cannot tolerate unhandled exceptions or service halts:
- **AI Timeout & Failure Handling**:
  - All calls to upstream AI services (Gemini API, STT, NLU) must have strict, non-blocking timeouts (recommended: 5.0 seconds maximum).
  - If the AI call times out, encounters HTTP 429/5xx, or returns malformed schema output:
    1. Immediately assign `requires_human_review = true` (and `needs_review = true`).
    2. Append specific diagnostic flags into `uncertainty_flags` (e.g., `["AI_TIMEOUT"]`, `["SCHEMA_VALIDATION_FAILURE"]`, or `["INSUFFICIENT_CALLER_DATA"]`).
    3. Retain the unparsed `caller_text` intact.
    4. Fall back to deterministic keyword-based heuristic categorization or flag the category as `UNKNOWN` for immediate manual dispatcher triage.
    5. Ensure the incident record transitions safely to `REPORTED` or `ASSESSED` with `needs_review = true` so dispatchers see the alert highlighted in real-time.
- **Zero Data Loss**:
  - Raw audio recordings, transcript fragments, coordinates, and timestamp logs must persist locally before asynchronous enrichment begins.
  - System crashes or network disconnects must not cause dropped emergencies; unacknowledged events automatically re-surface on dispatcher queues.

---

## 4. Contract Schema Invariance
- All inter-service communications (API requests, WebSocket messages, task queue payloads, database serializations) must strictly conform to versioned JSON Schemas stored under `contracts/`:
  - `incident.schema.json`
  - `assessment.schema.json`
  - `recommendation.schema.json`
  - `dispatch.schema.json`
- Any contract modification requires an explicit schema migration and version bump.
