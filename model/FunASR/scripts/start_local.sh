#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_DIR="$DEPLOY_DIR/funasr_source_code"
VENV_DIR="$DEPLOY_DIR/.venv"

if [ ! -f "$SOURCE_DIR/setup.py" ]; then
  echo "funasr_source_code/setup.py not found. Please check folder layout."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found in PATH"
  exit 1
fi

cd "$DEPLOY_DIR"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

PY_BIN="$VENV_DIR/bin/python"

"$PY_BIN" -m pip install --upgrade pip
"$PY_BIN" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
"$PY_BIN" -m pip install -e "$SOURCE_DIR"
"$PY_BIN" -m pip install -r "$DEPLOY_DIR/requirements-service.txt"

export MODEL_NAME="${MODEL_NAME:-paraformer-zh}"
export VAD_MODEL="${VAD_MODEL:-fsmn-vad}"
export PUNC_MODEL="${PUNC_MODEL:-ct-punc}"
export DEVICE="${DEVICE:-cpu}"
export BATCH_SIZE_S="${BATCH_SIZE_S:-300}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-10095}"

cd "$DEPLOY_DIR"
exec "$PY_BIN" -m uvicorn app.server:app --host "$HOST" --port "$PORT"
