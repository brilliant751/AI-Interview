#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_VENV="${BACKEND_VENV:-$ROOT_DIR/.venv}"
BACKEND_PYTHON="$BACKEND_VENV/bin/python"
BACKEND_UVICORN="$BACKEND_VENV/bin/uvicorn"
BACKEND_DB="$BACKEND_DIR/assets/data/sqlite/interview.db"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
START_FRONTEND="${START_FRONTEND:-1}"
BACKEND_RELOAD="${BACKEND_RELOAD:-0}"
MODELSCOPE_CACHE_DIR="$BACKEND_DIR/.cache/modelscope"
MODELSCOPE_DOMAIN_VALUE="${AI_INTERVIEW_MODELSCOPE_DOMAIN:-www.modelscope.cn}"
MODELSCOPE_DOWNLOAD_PARALLELS_VALUE="${AI_INTERVIEW_MODELSCOPE_DOWNLOAD_PARALLELS:-4}"
MODELSCOPE_PARALLEL_THRESHOLD_MB_VALUE="${AI_INTERVIEW_MODELSCOPE_PARALLEL_DOWNLOAD_THRESHOLD_MB:-50}"
HF_ENDPOINT_VALUE="${AI_INTERVIEW_HF_ENDPOINT:-}"
DISABLE_SYSTEM_PROXY_FOR_LOCAL_PROVIDER="${AI_INTERVIEW_DISABLE_SYSTEM_PROXY_FOR_LOCAL_PROVIDER:-1}"

OLLAMA_BASE_URL="${AI_INTERVIEW_OLLAMA_BASE_URL:-http://localhost:11434}"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

ensure_backend_python() {
  local python_bin="${PYTHON_BIN:-}"
  if [[ -z "$python_bin" ]]; then
    if command -v python3.11 >/dev/null 2>&1; then
      python_bin="$(command -v python3.11)"
    else
      python_bin="$(command -v python3)"
    fi
  fi
  if [[ -z "$python_bin" ]]; then
    echo "未找到可用 Python，请先安装 Python 3.11+。"
    exit 1
  fi
  if [[ ! -x "$BACKEND_PYTHON" ]]; then
    "$python_bin" -m venv "$BACKEND_VENV"
  fi
  if ! "$BACKEND_PYTHON" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(1)
PY
  then
    if command -v python3.11 >/dev/null 2>&1; then
      echo "[提示] 检测到现有虚拟环境 Python < 3.11，正在使用 python3.11 重建虚拟环境..."
      rm -rf "$BACKEND_VENV"
      python3.11 -m venv "$BACKEND_VENV"
      if ! "$BACKEND_PYTHON" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(1)
PY
      then
        echo "虚拟环境重建后 Python 版本仍低于 3.11，请检查本机 python3.11 安装。"
        exit 1
      fi
    else
      echo "当前虚拟环境 Python 版本低于 3.11，且未找到 python3.11。请先安装 Python 3.11+。"
      exit 1
    fi
  fi
}

release_occupied_ports() {
  local ports=("$BACKEND_PORT")
  if [[ "$START_FRONTEND" == "1" ]]; then
    ports+=("$FRONTEND_PORT")
  fi
  local port
  local pids
  local pid
  for port in "${ports[@]}"; do
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
    if [[ -n "$pids" ]]; then
      echo "[提示] 检测到端口 ${port} 被占用，正在释放..."
      for pid in $pids; do
        kill "$pid" 2>/dev/null || true
      done
      sleep 1
      pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
      if [[ -n "$pids" ]]; then
        for pid in $pids; do
          kill -9 "$pid" 2>/dev/null || true
        done
      fi
    fi
  done
}

ensure_backend_dependencies() {
  if ! "$BACKEND_PYTHON" -m pip --version >/dev/null 2>&1; then
    echo "[提示] 检测到虚拟环境缺少 pip，正在自动修复..."
    "$BACKEND_PYTHON" -m ensurepip --upgrade
  fi
  "$BACKEND_PYTHON" -m pip install --upgrade pip >/dev/null
  "$BACKEND_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt"
  "$BACKEND_PYTHON" -m pip install pytest ruff
}

prepare_model_cache_dirs() {
  mkdir -p "$MODELSCOPE_CACHE_DIR"
  export MODELSCOPE_CACHE="$MODELSCOPE_CACHE_DIR"
  export MODELSCOPE_DOMAIN="$MODELSCOPE_DOMAIN_VALUE"
  export MODELSCOPE_DOWNLOAD_PARALLELS="$MODELSCOPE_DOWNLOAD_PARALLELS_VALUE"
  export MODELSCOPE_PARALLEL_DOWNLOAD_THRESHOLD_MB="$MODELSCOPE_PARALLEL_THRESHOLD_MB_VALUE"
  export HF_HOME="$BACKEND_DIR/.cache/huggingface"
  mkdir -p "$HF_HOME"
  if [[ -n "$HF_ENDPOINT_VALUE" ]]; then
    export HF_ENDPOINT="$HF_ENDPOINT_VALUE"
  fi
}

ensure_frontend_dependencies() {
  if [[ "$START_FRONTEND" != "1" ]]; then
    return 0
  fi
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    (cd "$FRONTEND_DIR" && npm install)
  fi
}

ensure_initial_data() {
  if [[ ! -f "$BACKEND_DB" ]]; then
    "$BACKEND_PYTHON" "$BACKEND_DIR/assets/scripts/data/validate_materials.py" --strict
    "$BACKEND_PYTHON" "$BACKEND_DIR/assets/scripts/data/normalize_materials.py"
    "$BACKEND_PYTHON" "$BACKEND_DIR/assets/scripts/data/build_question_bank.py"
    "$BACKEND_PYTHON" "$BACKEND_DIR/assets/scripts/data/build_knowledge_vectorstore.py"
  fi
}

configure_proxy_for_local_providers() {
  if [[ "$DISABLE_SYSTEM_PROXY_FOR_LOCAL_PROVIDER" != "1" ]]; then
    return 0
  fi
  unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy ALL_PROXY all_proxy
  export NO_PROXY="${NO_PROXY:-}127.0.0.1,localhost"
  export no_proxy="${no_proxy:-}127.0.0.1,localhost"
}

check_local_ai_readiness() {
  local failed=0

  if ! curl -fsS "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
    echo "[提示] Ollama 不可达：${OLLAMA_BASE_URL}，将可能回退到模板模式。"
    failed=1
  fi

  if ! "$BACKEND_PYTHON" - <<'PY' >/dev/null 2>&1
import importlib.util

required = ["funasr", "paddlespeech"]
missing = [name for name in required if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit(1)
PY
  then
    echo "[提示] 未检测到 FunASR/PaddleSpeech SDK 依赖，语音能力将可能降级。"
    failed=1
  fi

  if [[ "$failed" -eq 0 ]]; then
    echo "本地模型服务检查通过。"
  fi
}

echo "[1/4] 准备后端环境..."
release_occupied_ports
ensure_backend_python
ensure_backend_dependencies
prepare_model_cache_dirs
configure_proxy_for_local_providers

echo "[2/4] 准备前端环境..."
ensure_frontend_dependencies

echo "[3/4] 初始化数据..."
ensure_initial_data

echo "[额外检查] 本地模型服务可达性..."
check_local_ai_readiness

echo "[4/4] 启动服务..."
if [[ "$BACKEND_RELOAD" == "1" ]]; then
  PYTHONPATH="$BACKEND_DIR" "$BACKEND_UVICORN" app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload &
else
  PYTHONPATH="$BACKEND_DIR" "$BACKEND_UVICORN" app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
fi
BACKEND_PID=$!

wait_for_backend_ready() {
  local retries=60
  while (( retries > 0 )); do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
      wait "$BACKEND_PID"
      return 1
    fi
    if "$BACKEND_PYTHON" - <<PY >/dev/null 2>&1
import socket

with socket.create_connection(("127.0.0.1", int("${BACKEND_PORT}")), timeout=1):
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

if ! wait_for_backend_ready; then
  echo "后端启动失败，已停止。"
  exit 1
fi

if [[ "$START_FRONTEND" == "1" ]]; then
  (cd "$FRONTEND_DIR" && npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT") &
  FRONTEND_PID=$!
fi

echo "后端：http://localhost:${BACKEND_PORT}"
if [[ "$START_FRONTEND" == "1" ]]; then
  echo "前端：http://localhost:${FRONTEND_PORT}"
else
  echo "前端：已跳过（START_FRONTEND=0）"
fi
echo "按 Ctrl+C 可同时停止两个服务。"

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID" || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
    echo "后端进程已退出，启动失败。"
    exit 1
  fi
  if [[ "$START_FRONTEND" == "1" ]]; then
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
      wait "$FRONTEND_PID" || true
      kill "$BACKEND_PID" 2>/dev/null || true
      wait "$BACKEND_PID" 2>/dev/null || true
      echo "前端进程已退出，启动失败。"
      exit 1
    fi
  fi
  sleep 1
done
