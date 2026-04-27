#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_VENV="$BACKEND_DIR/.venv"
BACKEND_PYTHON="$BACKEND_VENV/bin/python"
BACKEND_UVICORN="$BACKEND_VENV/bin/uvicorn"
BACKEND_DB="$ROOT_DIR/assets/data/sqlite/interview.db"
MODELSCOPE_CACHE_DIR="$BACKEND_DIR/.cache/modelscope"
MODELSCOPE_DOMAIN_VALUE="${AI_INTERVIEW_MODELSCOPE_DOMAIN:-www.modelscope.cn}"
MODELSCOPE_DOWNLOAD_PARALLELS_VALUE="${AI_INTERVIEW_MODELSCOPE_DOWNLOAD_PARALLELS:-4}"
MODELSCOPE_PARALLEL_THRESHOLD_MB_VALUE="${AI_INTERVIEW_MODELSCOPE_PARALLEL_DOWNLOAD_THRESHOLD_MB:-50}"
HF_ENDPOINT_VALUE="${AI_INTERVIEW_HF_ENDPOINT:-}"

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
  if [[ ! -x "$BACKEND_PYTHON" ]]; then
    python3 -m venv "$BACKEND_VENV"
  fi
}

release_occupied_ports() {
  local ports=("8000" "5173" "8173")
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
  "$BACKEND_PYTHON" -m pip install --upgrade pip >/dev/null
  "$BACKEND_PYTHON" -m pip install \
    fastapi \
    uvicorn[standard] \
    pydantic \
    pydantic-settings \
    python-multipart \
    openai \
    httpx \
    chromadb \
    langchain \
    langgraph \
    funasr \
    paddlespeech \
    soundfile \
    pytest \
    ruff
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
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    (cd "$FRONTEND_DIR" && npm install)
  fi
}

ensure_initial_data() {
  if [[ ! -f "$BACKEND_DB" ]]; then
    python3 "$ROOT_DIR/scripts/data/validate_materials.py" --strict
    python3 "$ROOT_DIR/scripts/data/normalize_materials.py"
    python3 "$ROOT_DIR/scripts/data/build_question_bank.py"
    python3 "$ROOT_DIR/scripts/data/build_knowledge_vectorstore.py"
  fi
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

echo "[2/4] 准备前端环境..."
ensure_frontend_dependencies

echo "[3/4] 初始化数据..."
ensure_initial_data

echo "[额外检查] 本地模型服务可达性..."
check_local_ai_readiness

echo "[4/4] 启动服务..."
PYTHONPATH="$BACKEND_DIR" "$BACKEND_UVICORN" app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

wait_for_backend_ready() {
  local retries=60
  while (( retries > 0 )); do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
      wait "$BACKEND_PID"
      return 1
    fi
    if python3 - <<'PY' >/dev/null 2>&1
import socket

with socket.create_connection(("127.0.0.1", 8000), timeout=1):
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

(cd "$FRONTEND_DIR" && npm run dev -- --host 0.0.0.0) &
FRONTEND_PID=$!

echo "后端：http://localhost:8000"
echo "前端：http://localhost:5173"
echo "按 Ctrl+C 可同时停止两个服务。"

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID" || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
    echo "后端进程已退出，启动失败。"
    exit 1
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    wait "$FRONTEND_PID" || true
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    echo "前端进程已退出，启动失败。"
    exit 1
  fi
  sleep 1
done
