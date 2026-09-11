$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactRoot = "E:\Escape\_AI"
$logRoot = Join-Path $artifactRoot "runs\champion-symmetry-ensemble-audit-launcher"
$runner = Join-Path $repoRoot ".venv\Scripts\escape-ai.exe"
$config = "configs\symmetry\champion-symmetry-ensemble-audit-17x17-v2.yaml"
$mutex = [System.Threading.Mutex]::new(
    $false,
    "Global\EscapeAIChampionSymmetryEnsembleAudit"
)
$ownsMutex = $false

try {
    $ownsMutex = $mutex.WaitOne(0)
    if (-not $ownsMutex) {
        throw "another champion symmetry-ensemble audit launcher is already running"
    }
    New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
    $startedAt = Get-Date -Format "yyyyMMdd-HHmmss"
    $logPath = Join-Path $logRoot "champion-symmetry-ensemble-audit-$startedAt.log"
    Start-Transcript -Path $logPath -Append | Out-Null

    Push-Location $repoRoot
    try {
        if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
            throw "Escape AI environment is missing: $runner"
        }
        $dirty = git status --porcelain
        if ($dirty) {
            throw "formal champion symmetry-ensemble audit requires a clean worktree"
        }
        $commit = git rev-parse HEAD
        Write-Host "Starting champion symmetry-ensemble audit from commit $commit"
        & $runner run-symmetry-audit --config $config
        if ($LASTEXITCODE -ne 0) {
            throw "champion symmetry-ensemble audit failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    try { Stop-Transcript | Out-Null } catch { }
    if ($ownsMutex) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
