param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$BackendVenv = if ($env:BACKEND_VENV) { $env:BACKEND_VENV } else { Join-Path $RootDir ".venv" }
$BackendPython = Join-Path $BackendVenv "Scripts\python.exe"
$BackendHost = if ($env:BACKEND_HOST) { $env:BACKEND_HOST } else { "0.0.0.0" }
$BackendPort = if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 18500 }
$FrontendHost = if ($env:FRONTEND_HOST) { $env:FRONTEND_HOST } else { "0.0.0.0" }
$FrontendPort = if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 5173 }
$StartFrontend = if ($env:START_FRONTEND) { $env:START_FRONTEND } else { "1" }
$BackendReload = if ($env:BACKEND_RELOAD) { $env:BACKEND_RELOAD } else { "0" }
$SkipInstall = if ($env:SKIP_INSTALL) { $env:SKIP_INSTALL } else { "0" }
$SkipDataInit = if ($env:SKIP_DATA_INIT) { $env:SKIP_DATA_INIT } else { "0" }
$ViteApiBase = if ($env:VITE_API_BASE) { $env:VITE_API_BASE } else { "http://localhost:$BackendPort/api/v1" }
$BackendDb = if ($env:AI_INTERVIEW_DB_PATH) { $env:AI_INTERVIEW_DB_PATH } else { Join-Path $BackendDir "assets\data\sqlite\interview.db" }

function Write-Log($Message) {
  Write-Host "[ai-interview] $Message"
}

function Fail($Message) {
  Write-Error "[ai-interview][error] $Message"
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

function Test-PythonVersion($PythonCommand) {
  Invoke-Python $PythonCommand @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)")
  return $LASTEXITCODE -eq 0
}

function Ensure-PythonVenv {
  $python = Find-Python
  if (-not $python) { Fail "未找到可用 Python，请安装 Python 3.11+。" }
  if (-not (Test-PythonVersion $python)) { Fail "Python 版本必须 >= 3.11。当前解释器：$python" }
  if (-not (Test-Path $BackendPython)) {
    Write-Log "创建后端虚拟环境：$BackendVenv"
    Invoke-Python $python @("-m", "venv", $BackendVenv)
  }
  & $BackendPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
  if ($LASTEXITCODE -ne 0) { Fail "虚拟环境 Python 版本低于 3.11，请删除 $BackendVenv 后重试。" }
}

function Ensure-Node {
  if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Fail "未找到 Node.js，请安装 Node.js 18+。" }
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Fail "未找到 npm，请安装 npm 9+。" }
  node -e "const v=process.versions.node.split('.').map(Number); process.exit(v[0] >= 18 ? 0 : 1)"
  if ($LASTEXITCODE -ne 0) { Fail "Node.js 版本必须 >= 18。当前版本：$(node --version)" }
  $npmMajor = [int]((npm -v).Split(".")[0])
  if ($npmMajor -lt 9) { Fail "npm 版本必须 >= 9。当前版本：$(npm -v)" }
}

function Install-Dependencies {
  if ($SkipInstall -eq "1") {
    Write-Log "跳过依赖安装（SKIP_INSTALL=1）。"
    return
  }
  Write-Log "安装后端依赖：backend/requirements.txt"
  & $BackendPython -m pip install --upgrade pip
  & $BackendPython -m pip install -r (Join-Path $BackendDir "requirements.txt")
  if ($StartFrontend -eq "1") {
    Write-Log "安装前端依赖：frontend/package.json"
    Push-Location $FrontendDir
    try {
      if (Test-Path "package-lock.json") { npm ci } else { npm install }
    } finally {
      Pop-Location
    }
  }
}

function Ensure-Data {
  if ($SkipDataInit -eq "1") {
    Write-Log "跳过数据初始化（SKIP_DATA_INIT=1）。"
    return
  }
  if (Test-Path $BackendDb) {
    Write-Log "检测到数据库已存在，跳过首次数据初始化：$BackendDb"
    return
  }
  Write-Log "首次初始化题库与知识库数据。"
  & $BackendPython (Join-Path $BackendDir "assets\scripts\data\validate_materials.py") --strict
  & $BackendPython (Join-Path $BackendDir "assets\scripts\data\normalize_materials.py")
  & $BackendPython (Join-Path $BackendDir "assets\scripts\data\build_question_bank.py")
  & $BackendPython (Join-Path $BackendDir "assets\scripts\data\build_knowledge_vectorstore.py")
}

function Test-PortAvailable([int]$Port) {
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
    $connected = $async.AsyncWaitHandle.WaitOne(300)
    if ($connected -and $client.Connected) { return $false }
    return $true
  } finally {
    $client.Close()
  }
}

function Wait-Port([int]$Port) {
  for ($i = 0; $i -lt 60; $i++) {
    if (-not (Test-PortAvailable $Port)) { return $true }
    Start-Sleep -Seconds 1
  }
  return $false
}

function New-BackendJob {
  $args = @("-m", "uvicorn", "app.main:app", "--host", $BackendHost, "--port", "$BackendPort")
  if ($BackendReload -eq "1") { $args += "--reload" }
  Start-Job -Name "ai-interview-backend" -ScriptBlock {
    param($Python, $BackendPath, $UvicornArgs)
    $env:PYTHONPATH = $BackendPath
    & $Python @UvicornArgs
  } -ArgumentList $BackendPython, $BackendDir, $args
}

function New-FrontendJob {
  Start-Job -Name "ai-interview-frontend" -ScriptBlock {
    param($FrontendPath, $HostValue, $PortValue, $ApiBase)
    $env:VITE_API_BASE = $ApiBase
    Set-Location $FrontendPath
    npm run dev -- --host $HostValue --port $PortValue
  } -ArgumentList $FrontendDir, $FrontendHost, "$FrontendPort", $ViteApiBase
}

$jobs = @()
try {
  Write-Log "仓库根目录：$RootDir"
  Clear-InvalidProxyEnv
  Ensure-PythonVenv
  Ensure-Node
  Install-Dependencies
  Ensure-Data
  if (-not (Test-PortAvailable $BackendPort)) { Fail "后端端口 $BackendPort 已被占用，请设置 BACKEND_PORT 或释放端口。" }
  $jobs += New-BackendJob
  if (-not (Wait-Port $BackendPort)) { Fail "后端启动超时，请检查日志。" }
  if ($StartFrontend -eq "1") {
    if (-not (Test-PortAvailable $FrontendPort)) { Fail "前端端口 $FrontendPort 已被占用，请设置 FRONTEND_PORT 或释放端口。" }
    $jobs += New-FrontendJob
  }
  Write-Log "后端接口文档：http://localhost:$BackendPort/docs"
  if ($StartFrontend -eq "1") { Write-Log "前端页面：http://localhost:$FrontendPort" }
  Write-Log "按 Ctrl+C 可停止所有子进程。"
  while ($true) {
    foreach ($job in $jobs) {
      Receive-Job $job | Write-Host
      if ($job.State -notin @("Running", "NotStarted")) {
        Receive-Job $job | Write-Host
        Fail "子进程已退出：$($job.Name) / $($job.State)"
      }
    }
    Start-Sleep -Seconds 2
  }
} finally {
  foreach ($job in $jobs) {
    Stop-Job $job -ErrorAction SilentlyContinue
    Remove-Job $job -Force -ErrorAction SilentlyContinue
  }
}
