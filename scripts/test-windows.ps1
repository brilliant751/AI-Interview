param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$BackendVenv = if ($env:BACKEND_VENV) { $env:BACKEND_VENV } else { Join-Path $RootDir ".venv" }
$BackendPython = Join-Path $BackendVenv "Scripts\python.exe"
$BackendRequirements = if ($env:BACKEND_REQUIREMENTS) { $env:BACKEND_REQUIREMENTS } else { Join-Path $BackendDir "requirements-ci.txt" }
$SkipInstall = if ($env:SKIP_INSTALL) { $env:SKIP_INSTALL } else { "0" }
$RunBackendTests = if ($env:RUN_BACKEND_TESTS) { $env:RUN_BACKEND_TESTS } else { "1" }
$RunFrontendTests = if ($env:RUN_FRONTEND_TESTS) { $env:RUN_FRONTEND_TESTS } else { "1" }
$RunE2E = if ($env:RUN_E2E) { $env:RUN_E2E } else { "1" }
$RunLint = if ($env:RUN_LINT) { $env:RUN_LINT } else { "1" }

function Write-Log($Message) {
  Write-Host "[ai-interview-test] $Message"
}

function Fail($Message) {
  Write-Error "[ai-interview-test][error] $Message"
  exit 1
}

function Clear-InvalidProxyEnv {
  foreach ($name in @("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")) {
    $value = [Environment]::GetEnvironmentVariable($name, "Process")
    if ($value -and $value -notmatch "^(https?|socks5h?)://") {
      Write-Log "检测到无效代理变量 $name=$value，已在当前脚本进程中清空。"
      [Environment]::SetEnvironmentVariable($name, $null, "Process")
    }
  }
}

function Find-Python {
  $candidates = @()
  if ($env:PYTHON_BIN) { $candidates += $env:PYTHON_BIN }
  $candidates += @("python3.11", "python3", "python")
  foreach ($candidate in $candidates) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
  }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return "py -3.11" }
  return $null
}

function Invoke-Python($PythonCommand, [string[]]$Arguments) {
  if ($PythonCommand -eq "py -3.11") {
    & py -3.11 @Arguments
  } else {
    & $PythonCommand @Arguments
  }
}

function Ensure-BackendEnv {
  $python = Find-Python
  if (-not $python) { Fail "未找到 Python 3.11+。" }
  Invoke-Python $python @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)")
  if ($LASTEXITCODE -ne 0) { Fail "Python 版本必须 >= 3.11。当前解释器：$python" }
  if (-not (Test-Path $BackendPython)) {
    Write-Log "创建测试虚拟环境：$BackendVenv"
    Invoke-Python $python @("-m", "venv", $BackendVenv)
  }
  if ($SkipInstall -ne "1") {
    Write-Log "安装后端测试依赖：$BackendRequirements"
    & $BackendPython -m pip install --upgrade pip
    & $BackendPython -m pip install -r $BackendRequirements
  }
}

function Ensure-FrontendEnv {
  if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Fail "未找到 Node.js，请安装 Node.js 18+。" }
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Fail "未找到 npm，请安装 npm 9+。" }
  node -e "const v=process.versions.node.split('.').map(Number); process.exit(v[0] >= 18 ? 0 : 1)"
  if ($LASTEXITCODE -ne 0) { Fail "Node.js 版本必须 >= 18。当前版本：$(node --version)" }
  $npmMajor = [int]((npm -v).Split(".")[0])
  if ($npmMajor -lt 9) { Fail "npm 版本必须 >= 9。当前版本：$(npm -v)" }
  if ($SkipInstall -ne "1") {
    Push-Location $FrontendDir
    try {
      if (Test-Path "package-lock.json") { npm ci } else { npm install }
    } finally {
      Pop-Location
    }
  }
}

Write-Log "仓库根目录：$RootDir"
Clear-InvalidProxyEnv
if ($RunBackendTests -eq "1" -or $RunLint -eq "1") {
  Ensure-BackendEnv
  if ($RunLint -eq "1") {
    Write-Log "运行后端 lint：ruff check backend tests"
    Push-Location $RootDir
    try { & $BackendPython -m ruff check backend tests } finally { Pop-Location }
  }
  if ($RunBackendTests -eq "1") {
    $backendTests = Get-ChildItem (Join-Path $RootDir "tests\backend") -Filter "test_*.py" -Recurse -ErrorAction SilentlyContinue
    if (-not $backendTests) {
      Write-Log "未发现后端测试文件，跳过。"
    } else {
      Write-Log "运行后端测试：pytest tests/backend"
      Push-Location $RootDir
      try { & $BackendPython -m pytest tests/backend } finally { Pop-Location }
    }
  }
}

if ($RunFrontendTests -eq "1" -or $RunE2E -eq "1" -or $RunLint -eq "1") {
  Ensure-FrontendEnv
  Push-Location $FrontendDir
  try {
    if ($RunLint -eq "1") {
      Write-Log "运行前端 lint：npm run lint"
      npm run lint
    }
    if ($RunFrontendTests -eq "1") {
      $unitTests = Get-ChildItem "src" -Include "*.test.ts","*.test.tsx" -Recurse -ErrorAction SilentlyContinue
      if (-not $unitTests) {
        Write-Log "未发现前端单元测试文件，跳过。"
      } else {
        Write-Log "运行前端单元测试：npm run test"
        npm run test
      }
      Write-Log "运行前端构建：npm run build"
      npm run build
    }
    if ($RunE2E -eq "1") {
      $e2eTests = Get-ChildItem "tests\e2e" -Filter "*.spec.ts" -Recurse -ErrorAction SilentlyContinue
      if (-not $e2eTests) {
        Write-Log "未发现 Playwright E2E 测试文件，跳过。"
      } else {
        if ($env:CI -eq "1") {
          Write-Log "CI 环境安装 Playwright Chromium。"
          npx playwright install --with-deps chromium
        }
        Write-Log "运行 Playwright E2E：npm run e2e"
        npm run e2e
      }
    }
  } finally {
    Pop-Location
  }
}

Write-Log "全部必跑检查通过。"
