#!/usr/bin/env bash
# =============================================================================
# SMART 112 - Local infrastructure health check
#
# Verifies that the PostGIS container is running, that PostgreSQL accepts
# connections, and that the spatial extension is actually installed and usable.
#
# Usage:
#   ./scripts/healthcheck.sh                 # single pass
#   ./scripts/healthcheck.sh --wait 60       # poll for up to 60s (useful right
#                                            # after `docker compose up -d`)
#   ./scripts/healthcheck.sh --verbose       # print every probe result
#
# Environment overrides (also read from .env when present):
#   SMART112_CONTAINER  container name        (default: smart112-postgres)
#   POSTGRES_USER       database user         (default: postgres)
#   POSTGRES_DB         database name         (default: smart112)
#   POSTGRES_HOST_PORT  host port (info only) (default: 5432)
#
# Exit codes: 0 = healthy, 1 = unhealthy, 2 = docker unavailable
# =============================================================================
set -uo pipefail

WAIT_SECONDS=0
VERBOSE=0
PASS_COUNT=0
FAIL_COUNT=0
FAILURE_DETAILS=()

# --- output helpers ----------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_GREEN="$(printf '\033[0;32m')"
  C_RED="$(printf '\033[0;31m')"
  C_YELLOW="$(printf '\033[0;33m')"
  C_CYAN="$(printf '\033[0;36m')"
  C_DIM="$(printf '\033[2m')"
  C_RESET="$(printf '\033[0m')"
else
  C_GREEN=""; C_RED=""; C_YELLOW=""; C_CYAN=""; C_DIM=""; C_RESET=""
fi

say()      { printf '%s\n' "$*"; }
detail()   { [ "$VERBOSE" -eq 1 ] && printf '    %s%s%s\n' "$C_DIM" "$*" "$C_RESET"; return 0; }

mark_pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf '  %s[PASS]%s %s\n' "$C_GREEN" "$C_RESET" "$1"
}

mark_fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  FAILURE_DETAILS+=("$1: $2")
  printf '  %s[FAIL]%s %s %s(%s)%s\n' "$C_RED" "$C_RESET" "$1" "$C_DIM" "$2" "$C_RESET"
}

# --- argument parsing --------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --wait)
      if [ $# -gt 1 ] && [[ "$2" =~ ^[0-9]+$ ]]; then
        WAIT_SECONDS="$2"; shift
      else
        WAIT_SECONDS=60
      fi
      ;;
    --wait=*)  WAIT_SECONDS="${1#*=}" ;;
    --timeout=*) WAIT_SECONDS="${1#*=}" ;;
    --verbose|-v) VERBOSE=1 ;;
    --help|-h)
      sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      say "Unknown option: $1 (try --help)"
      exit 2
      ;;
  esac
  shift
done

# --- optional .env loading (never overrides exported variables) --------------
load_env_value() {
  local key="$1" value
  [ -n "${!key:-}" ] && return 0
  [ -f .env ] || return 0
  value="$(grep -E "^[[:space:]]*${key}=" .env 2>/dev/null | tail -n 1 | cut -d= -f2-)"
  value="${value%$'\r'}"
  value="${value%\"}"; value="${value#\"}"
  [ -n "$value" ] && export "$key=$value"
  return 0
}

load_env_value SMART112_CONTAINER
load_env_value POSTGRES_USER
load_env_value POSTGRES_DB
load_env_value POSTGRES_HOST_PORT

CONTAINER_NAME="${SMART112_CONTAINER:-smart112-postgres}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-smart112}"
POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-5432}"

# --- probe helpers -----------------------------------------------------------
docker_available() {
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

container_state() {
  local state
  state="$(docker inspect --format '{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null | tr -d '\r\n')"
  [ -n "$state" ] || state="missing"
  printf '%s' "$state"
}

container_health() {
  local health
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
    "$CONTAINER_NAME" 2>/dev/null | tr -d '\r\n')"
  [ -n "$health" ] || health="unknown"
  printf '%s' "$health"
}

container_running() {
  [ "$(container_state)" = "running" ]
}

db_ping() {
  docker exec "$CONTAINER_NAME" pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1
}

sql_scalar() {
  docker exec "$CONTAINER_NAME" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "$1" 2>/dev/null \
    | tr -d '\r' \
    | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

db_ready() {
  [ "$(sql_scalar 'SELECT 1' 2>/dev/null)" = "1" ]
}

postgis_installed() {
  [ "$(sql_scalar "SELECT count(*) FROM pg_extension WHERE extname = 'postgis'")" = "1" ]
}

postgis_usable() {
  [ -n "$(sql_scalar 'SELECT postgis_version()')" ]
}

# --- wait mode ---------------------------------------------------------------
if [ "$WAIT_SECONDS" -gt 0 ]; then
  say "${C_CYAN}==>${C_RESET} Waiting up to ${WAIT_SECONDS}s for ${CONTAINER_NAME} to become healthy..."
  deadline=$((SECONDS + WAIT_SECONDS))
  while :; do
    if docker_available && container_running && db_ping && postgis_installed; then
      say "${C_GREEN}    container is healthy after $((WAIT_SECONDS - (deadline - SECONDS)))s${C_RESET}"
      break
    fi
    if [ "$SECONDS" -ge "$deadline" ]; then
      say "${C_RED}    timed out after ${WAIT_SECONDS}s${C_RESET}"
      break
    fi
    sleep 2
  done
fi

# --- report ------------------------------------------------------------------
say ""
say "${C_CYAN}SMART 112 :: local infrastructure healthcheck${C_RESET}"
say "  container: ${CONTAINER_NAME}   database: ${POSTGRES_DB}   user: ${POSTGRES_USER}   host port: ${POSTGRES_HOST_PORT}"
say ""

# 1. Docker engine
if ! command -v docker >/dev/null 2>&1; then
  mark_fail "Docker CLI" "not installed or not on PATH"
  say ""
  say "${C_RED}Docker is required. Install Docker Desktop and retry.${C_RESET}"
  exit 2
fi

if docker info >/dev/null 2>&1; then
  mark_pass "Docker engine reachable ($(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'unknown'))"
else
  mark_fail "Docker engine" "daemon not running"
  say ""
  say "${C_RED}Start Docker Desktop (or your docker daemon) and retry.${C_RESET}"
  exit 2
fi

# 2. Compose file present and valid
if [ -f docker-compose.yml ]; then
  if docker compose config >/dev/null 2>&1; then
    mark_pass "docker-compose.yml is valid"
  else
    mark_fail "docker-compose.yml" "compose configuration is invalid (run: docker compose config)"
  fi
else
  mark_fail "docker-compose.yml" "missing from the current directory"
fi

# 3. Container exists / running
state="$(container_state)"
if [ "$state" = "missing" ]; then
  mark_fail "Container '${CONTAINER_NAME}'" "not created (run: docker compose up -d postgres)"
else
  mark_pass "Container '${CONTAINER_NAME}' exists"
  if container_running; then
    mark_pass "Container is running"
    health="$(container_health)"
    if [ "$health" = "healthy" ]; then
      mark_pass "Docker healthcheck reports healthy"
    elif [ "$health" = "none" ]; then
      detail "No healthcheck defined on the container."
    else
      mark_fail "Docker healthcheck" "reports '${health}' (docker compose logs postgres)"
    fi
  else
    mark_fail "Container is running" "current state: ${state}"
  fi
fi

# 4. PostgreSQL responsiveness
if container_running; then
  if db_ping; then
    mark_pass "pg_isready accepted connections"
  else
    mark_fail "pg_isready" "server is not accepting connections"
  fi

  if db_ready; then
    mark_pass "SQL probe 'SELECT 1' succeeded (${POSTGRES_DB})"
  else
    mark_fail "SQL probe" "could not execute SELECT 1"
  fi

  if postgis_installed; then
    postgis_version="$(sql_scalar 'SELECT postgis_version()')"
    mark_pass "PostGIS extension installed (${postgis_version%% *})"
    detail "SRID 4326 geodesic distance available via geography casts."
    if postgis_usable; then
      mark_pass "PostGIS functions executable"
    else
      mark_fail "PostGIS functions" "postgis_version() failed"
    fi
  else
    mark_fail "PostGIS extension" "missing (run: docker compose exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c 'CREATE EXTENSION IF NOT EXISTS postgis;')"
  fi

  # 5. Application schema readiness (non-fatal: migrations may not have run yet)
  if [ "$(sql_scalar "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('incidents','emergency_units','dispatch_assignments','audit_logs')")" = "4" ]; then
    mark_pass "Application tables present (incidents, emergency_units, dispatch_assignments, audit_logs)"
    unit_count="$(sql_scalar 'SELECT count(*) FROM emergency_units')"
    detail "emergency_units rows: ${unit_count:-unknown}"
  else
    detail "Application tables not created yet (run: alembic upgrade head or start the API)."
  fi
fi

# --- summary -----------------------------------------------------------------
say ""
if [ "$FAIL_COUNT" -eq 0 ]; then
  say "${C_GREEN}RESULT: HEALTHY${C_RESET} (${PASS_COUNT} checks passed)"
  say "${C_DIM}API: http://localhost:8000/health   Database: postgresql://${POSTGRES_USER}@localhost:${POSTGRES_HOST_PORT}/${POSTGRES_DB}${C_RESET}"
  exit 0
fi

say "${C_RED}RESULT: UNHEALTHY${C_RESET} (${PASS_COUNT} passed, ${FAIL_COUNT} failed)"
for failure in "${FAILURE_DETAILS[@]}"; do
  say "  ${C_YELLOW}-${C_RESET} ${failure}"
done
say ""
say "Remediation:"
say "  1. docker compose up -d postgres"
say "  2. docker compose logs --tail=80 postgres"
say "  3. docker compose exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c 'CREATE EXTENSION IF NOT EXISTS postgis;'"
exit 1
