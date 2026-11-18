#!/bin/bash
# Start (or restart) the portfolio app: FastAPI backend on :8000,
# Vite/React frontend on :5173. Anything already listening on those
# ports is killed first, so this is safe to run repeatedly.

set -u

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=5173
LOG_DIR="$ROOT/.devin/skills/run-app/logs"
mkdir -p "$LOG_DIR"

stop_port() {
  local port=$1 pids
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "Port $port in use (pids: $(echo $pids | tr '\n' ' ')) — restarting"
    kill $pids 2>/dev/null || true
    sleep 1
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
      kill -9 $pids 2>/dev/null || true
      sleep 1
    fi
  fi
}

wait_for() {
  local url=$1 name=$2 tries=0
  until curl -sf -o /dev/null --max-time 2 "$url"; do
    tries=$((tries + 1))
    if [ "$tries" -ge 30 ]; then
      echo "ERROR: $name did not become ready. Check logs in $LOG_DIR"
      return 1
    fi
    sleep 1
  done
  echo "$name is up: $url"
}

# --- backend ---
stop_port $BACKEND_PORT
(cd "$ROOT/backend" && nohup ./venv/bin/uvicorn main:app --host 127.0.0.1 --port $BACKEND_PORT \
  > "$LOG_DIR/backend.log" 2>&1 &)
echo "Backend starting (log: $LOG_DIR/backend.log)"

# --- frontend ---
stop_port $FRONTEND_PORT
export PATH="$HOME/.local/node/bin:$PATH"
(cd "$ROOT/frontend" && nohup npm run dev -- --port $FRONTEND_PORT \
  > "$LOG_DIR/frontend.log" 2>&1 &)
echo "Frontend starting (log: $LOG_DIR/frontend.log)"

wait_for "http://127.0.0.1:$BACKEND_PORT/api/portfolio" "Backend" || exit 1
wait_for "http://localhost:$FRONTEND_PORT/" "Frontend" || exit 1

echo ""
echo "App is running:"
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  Backend:  http://localhost:$BACKEND_PORT  (docs: http://localhost:$BACKEND_PORT/docs)"
