$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactRoot = "E:\Escape\_AI"
$runId = "champion-raw-vs-d4-strength-17x17-v1"
$logRoot = Join-Path $artifactRoot "runs\champion-raw-vs-d4-strength-launcher"
$runner = Join-Path $repoRoot ".venv\Scripts\escape-ai.exe"
$config = "configs\games\champion-raw-vs-d4-strength-17x17-v1.yaml"
$games = "E:/Escape/_AI/games/$runId"
$analysis = "E:/Escape/_AI/runs/$runId/analysis.json"
$mutex = [System.Threading.Mutex]::new($false, "Global\EscapeAIChampionRawVsD4")
$ownsMutex = $false

try {
    $ownsMutex = $mutex.WaitOne(0)
    if (-not $ownsMutex) {
        throw "another champion raw-versus-D4 strength run is already running"
    }
    New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
    $startedAt = Get-Date -Format "yyyyMMdd-HHmmss"
    $logPath = Join-Path $logRoot "champion-raw-vs-d4-$startedAt.log"
    Start-Transcript -Path $logPath -Append | Out-Null

    Push-Location $repoRoot
    try {
        if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
            throw "Escape AI environment is missing: $runner"
        }
        $dirty = git status --porcelain
        if ($dirty) {
            throw "formal champion raw-versus-D4 match requires a clean worktree"
        }
        $commit = git rev-parse HEAD
        Write-Host "Starting or resuming raw-versus-D4 strength match from commit $commit"
        & $runner generate-research-games --config $config
        if ($LASTEXITCODE -ne 0) {
            throw "raw-versus-D4 game generation failed with exit code $LASTEXITCODE"
        }
        & $runner analyze-evaluator-match --input $games --output $analysis
        if ($LASTEXITCODE -ne 0) {
            throw "raw-versus-D4 analysis failed with exit code $LASTEXITCODE"
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
