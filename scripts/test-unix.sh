#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_VENV="${BACKEND_VENV:-$ROOT_DIR/.venv}"
BACKEND_PYTHON="$BACKEND_VENV/bin/python"
SKIP_INSTALL="${SKIP_INSTALL:-0}"
BACKEND_REQUIREMENTS="${BACKEND_REQUIREMENTS:-$BACKEND_DIR/requirements-ci.txt}"

if [[ "${CI:-0}" == "1" ]]; then
  RUN_BACKEND_TESTS="${RUN_BACKEND_TESTS:-1}"
  RUN_FRONTEND_TESTS="${RUN_FRONTEND_TESTS:-1}"
  RUN_E2E="${RUN_E2E:-1}"
  RUN_LINT="${RUN_LINT:-1}"
else
  RUN_BACKEND_TESTS="${RUN_BACKEND_TESTS:-1}"
  RUN_FRONTEND_TESTS="${RUN_FRONTEND_TESTS:-1}"
  RUN_E2E="${RUN_E2E:-1}"
  RUN_LINT="${RUN_LINT:-1}"
fi

log() {
  printf '[ai-interview-test] %s\n' "$*"
}

fail() {
  printf '[ai-interview-test][error] %s\n' "$*" >&2
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
  "$1" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

ensure_backend_env() {
  local python_bin
  python_bin="$(find_python)" || fail "未找到 Python 3.11+。"
  check_python_version "$python_bin" || fail "Python 版本必须 >= 3.11。当前解释器：$python_bin"
  if [[ ! -x "$BACKEND_PYTHON" ]]; then
    log "创建测试虚拟环境：$BACKEND_VENV"
    "$python_bin" -m venv "$BACKEND_VENV"
  fi
  check_python_version "$BACKEND_PYTHON" || fail "虚拟环境 Python 版本低于 3.11。"
  if [[ "$SKIP_INSTALL" != "1" ]]; then
    log "安装后端测试依赖：${BACKEND_REQUIREMENTS#$ROOT_DIR/}"
    "$BACKEND_PYTHON" -m pip install --upgrade pip
    "$BACKEND_PYTHON" -m pip install -r "$BACKEND_REQUIREMENTS"
  fi
}

ensure_frontend_env() {
  command -v node >/dev/null 2>&1 || fail "未找到 Node.js，请安装 Node.js 18+。"
  command -v npm >/dev/null 2>&1 || fail "未找到 npm，请安装 npm 9+。"
  node -e "const v=process.versions.node.split('.').map(Number); process.exit(v[0] >= 18 ? 0 : 1)" \
    || fail "Node.js 版本必须 >= 18。当前版本：$(node --version)"
  npm -v | awk -F. '{ exit ($1 >= 9 ? 0 : 1) }' \
    || fail "npm 版本必须 >= 9。当前版本：$(npm -v)"
  if [[ "$SKIP_INSTALL" != "1" ]]; then
    log "安装前端依赖。"
    if [[ -f "$FRONTEND_DIR/package-lock.json" ]]; then
      (cd "$FRONTEND_DIR" && npm ci)
    else
      (cd "$FRONTEND_DIR" && npm install)
    fi
  fi
}

run_backend_checks() {
  if [[ "$RUN_LINT" == "1" ]]; then
    log "运行后端 lint：ruff check backend tests"
    (cd "$ROOT_DIR" && "$BACKEND_PYTHON" -m ruff check backend tests)
  fi

  if [[ "$RUN_BACKEND_TESTS" == "1" ]]; then
    if ! find "$ROOT_DIR/tests/backend" -type f -name 'test_*.py' | grep -q .; then
      log "未发现后端测试文件，跳过。"
    else
      log "运行后端测试：pytest tests/backend"
      (cd "$ROOT_DIR" && "$BACKEND_PYTHON" -m pytest tests/backend)
    fi
  fi
}

run_frontend_checks() {
  if [[ "$RUN_LINT" == "1" ]]; then
    log "运行前端 lint：npm run lint"
    (cd "$FRONTEND_DIR" && npm run lint)
  fi

  if [[ "$RUN_FRONTEND_TESTS" == "1" ]]; then
    if ! find "$FRONTEND_DIR/src" -type f \( -name '*.test.ts' -o -name '*.test.tsx' \) | grep -q .; then
      log "未发现前端单元测试文件，跳过。"
    else
      log "运行前端单元测试：npm run test"
      (cd "$FRONTEND_DIR" && npm run test)
    fi
    log "运行前端构建：npm run build"
    (cd "$FRONTEND_DIR" && npm run build)
  fi

  if [[ "$RUN_E2E" == "1" ]]; then
    if ! find "$FRONTEND_DIR/tests/e2e" -type f -name '*.spec.ts' | grep -q .; then
      log "未发现 Playwright E2E 测试文件，跳过。"
    else
      if [[ "${CI:-0}" == "1" ]]; then
        log "CI 环境安装 Playwright Chromium。"
        (cd "$FRONTEND_DIR" && npx playwright install --with-deps chromium)
      fi
      log "运行 Playwright E2E：npm run e2e"
      (cd "$FRONTEND_DIR" && npm run e2e) || {
        log "如果提示浏览器未安装，请运行：cd frontend && npx playwright install --with-deps chromium"
        return 1
      }
    fi
  fi
}

main() {
  log "仓库根目录：$ROOT_DIR"
  sanitize_proxy_env
  if [[ "$RUN_BACKEND_TESTS" == "1" || "$RUN_LINT" == "1" ]]; then
    ensure_backend_env
    run_backend_checks
  fi
  if [[ "$RUN_FRONTEND_TESTS" == "1" || "$RUN_E2E" == "1" || "$RUN_LINT" == "1" ]]; then
    ensure_frontend_env
    run_frontend_checks
  fi
  log "全部必跑检查通过。"
}

main "$@"
