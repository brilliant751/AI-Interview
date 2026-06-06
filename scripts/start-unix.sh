#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_VENV="${BACKEND_VENV:-$ROOT_DIR/.venv}"
BACKEND_PYTHON="$BACKEND_VENV/bin/python"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-18500}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
START_FRONTEND="${START_FRONTEND:-1}"
BACKEND_RELOAD="${BACKEND_RELOAD:-0}"
SKIP_INSTALL="${SKIP_INSTALL:-0}"
SKIP_DATA_INIT="${SKIP_DATA_INIT:-0}"
VITE_API_BASE="${VITE_API_BASE:-http://localhost:${BACKEND_PORT}/api/v1}"
BACKEND_DB="${AI_INTERVIEW_DB_PATH:-$BACKEND_DIR/assets/data/sqlite/interview.db}"

BACKEND_PID=""
FRONTEND_PID=""

log() {
  printf '[ai-interview] %s\n' "$*"
}

fail() {
  printf '[ai-interview][error] %s\n' "$*" >&2
  exit 1
}

sanitize_proxy_env() {
  local name value
  for name in HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy; do
    value="${!name:-}"
    if [[ -n "$value" && "$value" != http://* && "$value" != https://* && "$value" != socks5://* && "$value" != socks5h://* ]]; then
      log "检测到无效代理变量 ${name}=${value}，已在当前脚本进程中清空。"
      unset "$name"
    fi
  done
}

cleanup() {
  local pid
  for pid in "$FRONTEND_PID" "$BACKEND_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}

trap cleanup EXIT INT TERM

find_python() {
  local candidate
  for candidate in "${PYTHON_BIN:-}" python3.11 python3 python; do
    if [[ -n "$candidate" ]] && command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

check_python_version() {
  local python_bin="$1"
  "$python_bin" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

check_node_version() {
  command -v node >/dev/null 2>&1 || fail "未找到 Node.js，请安装 Node.js 18+。"
  command -v npm >/dev/null 2>&1 || fail "未找到 npm，请安装 npm 9+。"
  node -e "const v=process.versions.node.split('.').map(Number); process.exit(v[0] >= 18 ? 0 : 1)" \
    || fail "Node.js 版本必须 >= 18。当前版本：$(node --version)"
  npm -v | awk -F. '{ exit ($1 >= 9 ? 0 : 1) }' \
    || fail "npm 版本必须 >= 9。当前版本：$(npm -v)"
}

ensure_python_venv() {
  local python_bin
  python_bin="$(find_python)" || fail "未找到可用 Python，请安装 Python 3.11+。"
  check_python_version "$python_bin" || fail "Python 版本必须 >= 3.11。当前解释器：$python_bin"

  if [[ ! -x "$BACKEND_PYTHON" ]]; then
    log "创建后端虚拟环境：$BACKEND_VENV"
    "$python_bin" -m venv "$BACKEND_VENV"
  fi

  check_python_version "$BACKEND_PYTHON" || fail "虚拟环境 Python 版本低于 3.11，请删除 $BACKEND_VENV 后重试。"
}

install_dependencies() {
  if [[ "$SKIP_INSTALL" == "1" ]]; then
    log "跳过依赖安装（SKIP_INSTALL=1）。"
    return 0
  fi

  log "安装后端依赖：backend/requirements.txt"
  "$BACKEND_PYTHON" -m pip install --upgrade pip
  "$BACKEND_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt"

  if [[ "$START_FRONTEND" == "1" ]]; then
    log "安装前端依赖：frontend/package.json"
    if [[ -f "$FRONTEND_DIR/package-lock.json" ]]; then
      (cd "$FRONTEND_DIR" && npm ci)
    else
      (cd "$FRONTEND_DIR" && npm install)
    fi
  fi
}

ensure_data() {
  if [[ "$SKIP_DATA_INIT" == "1" ]]; then
    log "跳过数据初始化（SKIP_DATA_INIT=1）。"
    return 0
  fi
  if [[ -f "$BACKEND_DB" ]]; then
    log "检测到数据库已存在，跳过首次数据初始化：$BACKEND_DB"
    return 0
  fi

  log "首次初始化题库与知识库数据。"
  "$BACKEND_PYTHON" "$BACKEND_DIR/assets/scripts/data/validate_materials.py" --strict
  "$BACKEND_PYTHON" "$BACKEND_DIR/assets/scripts/data/normalize_materials.py"
  "$BACKEND_PYTHON" "$BACKEND_DIR/assets/scripts/data/build_question_bank.py"
  "$BACKEND_PYTHON" "$BACKEND_DIR/assets/scripts/data/build_knowledge_vectorstore.py"
}

check_port_available() {
  local port="$1"
  "$BACKEND_PYTHON" - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket() as sock:
    raise SystemExit(1 if sock.connect_ex(("127.0.0.1", port)) == 0 else 0)
PY
}

wait_for_port() {
  local port="$1"
  local retries=60
  while (( retries > 0 )); do
    if "$BACKEND_PYTHON" - "$port" <<'PY' >/dev/null 2>&1
import socket
import sys

with socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=1):
    pass
PY
    then
      return 0
    fi
    sleep 1
    retries=$((retries - 1))
  done
  return 1
}

check_optional_local_models() {
  local ollama_url="${AI_INTERVIEW_OLLAMA_BASE_URL:-http://localhost:11434}"
  if command -v curl >/dev/null 2>&1; then
    if ! curl -fsS "${ollama_url}/api/tags" >/dev/null 2>&1; then
      log "提示：Ollama 不可达（${ollama_url}），系统会使用 mock/模板或前端展示降级状态。"
    fi
  fi
  "$BACKEND_PYTHON" - <<'PY' >/dev/null 2>&1 || true
import importlib.util

missing = [name for name in ("funasr", "paddlespeech") if importlib.util.find_spec(name) is None]
if missing:
    print("missing")
PY
}

start_backend() {
  check_port_available "$BACKEND_PORT" || fail "后端端口 ${BACKEND_PORT} 已被占用，请设置 BACKEND_PORT 或释放端口。"
  log "启动后端：http://localhost:${BACKEND_PORT}"
  if [[ "$BACKEND_RELOAD" == "1" ]]; then
    PYTHONPATH="$BACKEND_DIR" "$BACKEND_PYTHON" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload &
  else
    PYTHONPATH="$BACKEND_DIR" "$BACKEND_PYTHON" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
  fi
  BACKEND_PID=$!
  wait_for_port "$BACKEND_PORT" || fail "后端启动超时，请检查上方日志。"
}

start_frontend() {
  if [[ "$START_FRONTEND" != "1" ]]; then
    log "前端未启动（START_FRONTEND=0）。"
    return 0
  fi
  check_port_available "$FRONTEND_PORT" || fail "前端端口 ${FRONTEND_PORT} 已被占用，请设置 FRONTEND_PORT 或释放端口。"
  log "启动前端：http://localhost:${FRONTEND_PORT}"
  (cd "$FRONTEND_DIR" && VITE_API_BASE="$VITE_API_BASE" npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT") &
  FRONTEND_PID=$!
}

main() {
  log "仓库根目录：$ROOT_DIR"
  sanitize_proxy_env
  ensure_python_venv
  check_node_version
  install_dependencies
  ensure_data
  check_optional_local_models
  start_backend
  start_frontend

  log "后端接口文档：http://localhost:${BACKEND_PORT}/docs"
  if [[ "$START_FRONTEND" == "1" ]]; then
    log "前端页面：http://localhost:${FRONTEND_PORT}"
  fi
  log "按 Ctrl+C 可停止所有子进程。"

  while true; do
    if [[ -n "$BACKEND_PID" ]] && ! kill -0 "$BACKEND_PID" 2>/dev/null; then
      wait "$BACKEND_PID" || true
      fail "后端进程已退出。"
    fi
    if [[ "$START_FRONTEND" == "1" ]] && [[ -n "$FRONTEND_PID" ]] && ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
      wait "$FRONTEND_PID" || true
      fail "前端进程已退出。"
    fi
    sleep 2
  done
}

main "$@"
