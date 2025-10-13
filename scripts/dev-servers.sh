#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
BACKEND_PORT=${BACKEND_PORT:-8890}
FRONTEND_PORT=${FRONTEND_PORT:-5173}

function warn() {
  echo "[dev-servers] $*" >&2
}

if [[ -f "${ENV_FILE}" ]]; then
  warn "Loading environment from ${ENV_FILE}"
  # shellcheck disable=SC1090
  set -a && source "${ENV_FILE}" && set +a
else
  warn "No .env file found at ${ENV_FILE}; relying on current environment"
fi

cd "${ROOT_DIR}" || exit 1

function kill_port_if_busy() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids=$(lsof -ti tcp:"${port}" || true)
    if [[ -n "${pids}" ]]; then
      warn "Port ${port} is busy (PID(s): ${pids}); terminating before restart"
      kill ${pids} >/dev/null 2>&1 || true
      sleep 1
    fi
  else
    warn "lsof not available; unable to automatically free port ${port}"
  fi
}

function shutdown() {
  warn "Shutting down dev servers..."
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}"
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    kill "${FRONTEND_PID}"
    wait "${FRONTEND_PID}" 2>/dev/null || true
  fi
}

trap shutdown EXIT INT TERM

warn "Starting FastAPI backend on port ${BACKEND_PORT}"
kill_port_if_busy "${BACKEND_PORT}"
.venv/bin/uvicorn api.main:app --reload --port "${BACKEND_PORT}" --env-file "${ENV_FILE}" &
BACKEND_PID=$!

warn "Starting SvelteKit frontend on port ${FRONTEND_PORT}"
kill_port_if_busy "${FRONTEND_PORT}"
cd "${ROOT_DIR}/frontend" || exit 1
if command -v pnpm >/dev/null 2>&1; then
  pnpm install >/dev/null
  pnpm run dev -- --host --port "${FRONTEND_PORT}" &
else
  npm install >/dev/null
  npm run dev -- --host --port "${FRONTEND_PORT}" &
fi
FRONTEND_PID=$!

wait
