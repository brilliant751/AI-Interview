#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

cleanup() {
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

release_frontend_port() {
  local pids
  local pid
  pids="$(lsof -tiTCP:"$FRONTEND_PORT" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
  if [[ -n "$pids" ]]; then
    echo "[提示] 检测到前端端口 ${FRONTEND_PORT} 被占用，正在释放..."
    for pid in $pids; do
      kill "$pid" 2>/dev/null || true
    done
    sleep 1
    pids="$(lsof -tiTCP:"$FRONTEND_PORT" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
    if [[ -n "$pids" ]]; then
      for pid in $pids; do
        kill -9 "$pid" 2>/dev/null || true
      done
    fi
  fi
}

ensure_frontend_dependencies() {
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    (cd "$FRONTEND_DIR" && npm install)
  fi
}

echo "[1/2] 准备前端环境..."
release_frontend_port
ensure_frontend_dependencies

echo "[2/2] 启动前端服务..."
(cd "$FRONTEND_DIR" && npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT") &
FRONTEND_PID=$!

echo "前端：http://localhost:${FRONTEND_PORT}"
echo "按 Ctrl+C 可停止前端服务。"

wait "$FRONTEND_PID"

