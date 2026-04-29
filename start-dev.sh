#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_PID=""
FRONTEND_PID=""
BACKEND_PORT="8000"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
FRONTEND_PORT="5173"
BACKEND_RELOAD="${BACKEND_RELOAD:-0}"
BACKEND_PYTHON=""
START_FRONTEND="${START_FRONTEND:-1}"

# 校验命令是否存在。
check_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[错误] 未找到命令: $cmd"
    exit 1
  fi
}

# 释放被占用端口，避免启动失败。
free_port_if_occupied() {
  local port="$1"
  local pids
  local retries=5
  local attempt=1

  pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi

  echo "[信息] 端口 $port 已被占用，正在结束进程: $pids"
  kill $pids >/dev/null 2>&1 || true
  sleep 0.5

  # 若进程仍存在，强制结束。
  pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "[信息] 端口 $port 仍被占用，正在强制结束进程: $pids"
    kill -9 $pids >/dev/null 2>&1 || true
  fi

  # 等待端口释放，避免后续立即启动时偶发冲突。
  while (( attempt <= retries )); do
    pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)"
    if [[ -z "$pids" ]]; then
      echo "[信息] 端口 $port 已释放"
      return 0
    fi
    sleep 0.5
    ((attempt++))
  done

  echo "[错误] 端口 $port 释放失败。"
  return 1
}

# 校验端口是否可绑定，防止存在 lsof 未捕获的占用场景。
ensure_port_bindable() {
  local host="$1"
  local port="$2"
  "$BACKEND_PYTHON" - <<PY >/dev/null 2>&1
import socket
host = "${host}"
port = int("${port}")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind((host, port))
finally:
    s.close()
PY
}

# 在收到退出信号时，关闭前后端进程。
cleanup() {
  echo "[信息] 正在停止前后端服务..."
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" >/dev/null 2>&1; then
    kill "${FRONTEND_PID}" >/dev/null 2>&1 || true
  fi
}

# 启动后端 FastAPI 开发服务。
start_backend() {
  (
    cd "$BACKEND_DIR"
    if [[ "$BACKEND_RELOAD" == "1" ]]; then
      echo "[信息] 后端启用热重载模式"
      PYTHONPATH="$BACKEND_DIR" "$BACKEND_PYTHON" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload
    else
      echo "[信息] 后端启用普通模式（未开启热重载）"
      PYTHONPATH="$BACKEND_DIR" "$BACKEND_PYTHON" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT"
    fi
  )
}

# 启动前端 Vite 开发服务。
start_frontend() {
  (
    cd "$FRONTEND_DIR"
    npm run dev
  )
}

main() {
  check_command python3
  check_command npm
  check_command lsof

  if [[ ! -d "$BACKEND_DIR" ]]; then
    echo "[错误] 未找到后端目录: $BACKEND_DIR"
    exit 1
  fi

  if [[ ! -d "$FRONTEND_DIR" ]]; then
    echo "[错误] 未找到前端目录: $FRONTEND_DIR"
    exit 1
  fi

  if [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
    BACKEND_PYTHON="$BACKEND_DIR/.venv/bin/python"
  else
    BACKEND_PYTHON="$(command -v python3)"
  fi
  echo "[信息] 使用 Python 解释器: $BACKEND_PYTHON"

  if ! free_port_if_occupied "$BACKEND_PORT"; then
    echo "[错误] 后端端口 ${BACKEND_PORT} 无法释放，启动终止。"
    lsof -nP -iTCP:"$BACKEND_PORT" -sTCP:LISTEN || true
    netstat -anv -p tcp | grep "[\.\:]${BACKEND_PORT} .*LISTEN" || true
    exit 1
  fi
  if ! ensure_port_bindable "$BACKEND_HOST" "$BACKEND_PORT"; then
    echo "[错误] 后端地址 ${BACKEND_HOST}:${BACKEND_PORT} 不可绑定，启动终止。"
    lsof -nP -iTCP:"$BACKEND_PORT" -sTCP:LISTEN || true
    netstat -anv -p tcp | grep "[\.\:]${BACKEND_PORT} .*LISTEN" || true
    exit 1
  fi
  if [[ "$START_FRONTEND" == "1" ]]; then
    if ! free_port_if_occupied "$FRONTEND_PORT"; then
      echo "[警告] 前端端口 ${FRONTEND_PORT} 无法释放，将继续尝试启动后端。"
    fi
  fi

  trap cleanup EXIT INT TERM

  echo "[信息] 启动后端服务: http://${BACKEND_HOST}:${BACKEND_PORT}/docs"
  start_backend &
  BACKEND_PID=$!

  if [[ "$START_FRONTEND" == "1" ]]; then
    echo "[信息] 启动前端服务: http://localhost:${FRONTEND_PORT}"
    start_frontend &
    FRONTEND_PID=$!
  else
    echo "[信息] 已跳过前端启动（START_FRONTEND=0）"
  fi

  echo "[信息] 前后端已启动，按 Ctrl+C 停止。"
  if [[ -n "$FRONTEND_PID" ]]; then
    wait "$BACKEND_PID" "$FRONTEND_PID"
  else
    wait "$BACKEND_PID"
  fi
}

main "$@"
