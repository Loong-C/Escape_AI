$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $repoRoot ".venv"

if (-not (Test-Path -LiteralPath $venvPath)) {
    python -m venv $venvPath --system-site-packages
}

$pythonPath = Join-Path $venvPath "Scripts\python.exe"
$constraintsPath = Join-Path $repoRoot "requirements\constraints-win-cu128.txt"
& $pythonPath -m pip install --upgrade pip
& $pythonPath -m pip install --constraint $constraintsPath -e "$repoRoot[dev,research,server]"
& $pythonPath -c "from escape_ai.paths import ensure_artifact_layout; print(ensure_artifact_layout())"
