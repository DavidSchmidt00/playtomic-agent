#!/usr/bin/env bash
set -euo pipefail

# Start the backend
uvicorn playtomic_agent.api:app --host 0.0.0.0 --port 8082 &
backend_pid=$!

# Start frontend dev server
(cd web && npm run dev -- --port 8080)

# On exit, kill backend
trap "kill ${backend_pid} 2>/dev/null || true" EXIT
