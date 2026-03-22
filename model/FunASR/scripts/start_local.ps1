Param(
    [string]$Host = "0.0.0.0",
    [int]$Port = 10095
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$deployDir = Resolve-Path (Join-Path $scriptDir "..")
$sourceDir = Resolve-Path (Join-Path $deployDir "funasr_source_code")
$venvPath = Join-Path $deployDir ".venv"

if (-not (Test-Path (Join-Path $sourceDir "setup.py"))) {
    throw "funasr_source_code/setup.py not found. Please check folder layout."
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python not found in PATH."
}

Set-Location $deployDir

if (-not (Test-Path $venvPath)) {
    python -m venv $venvPath
}

$py = Join-Path $venvPath "Scripts\python.exe"

& $py -m pip install --upgrade pip
& $py -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
& $py -m pip install -e $sourceDir
& $py -m pip install -r (Join-Path $deployDir "requirements-service.txt")

if (-not $env:MODEL_NAME) { $env:MODEL_NAME = "paraformer-zh" }
if (-not $env:VAD_MODEL) { $env:VAD_MODEL = "fsmn-vad" }
if (-not $env:PUNC_MODEL) { $env:PUNC_MODEL = "ct-punc" }
if (-not $env:DEVICE) { $env:DEVICE = "cpu" }
if (-not $env:BATCH_SIZE_S) { $env:BATCH_SIZE_S = "300" }

Set-Location $deployDir
& $py -m uvicorn app.server:app --host $Host --port $Port
