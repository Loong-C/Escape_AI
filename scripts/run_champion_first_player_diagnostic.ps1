$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactRoot = "E:\Escape\_AI"
$runId = "champion-first-player-diagnostic-17x17-v1"
$logRoot = Join-Path $artifactRoot "runs\champion-first-player-diagnostic-launcher"
$runner = Join-Path $repoRoot ".venv\Scripts\escape-ai.exe"
$config = "configs\games\champion-first-player-diagnostic-17x17-v1.yaml"
$games = "E:/Escape/_AI/games/$runId"
$analysis = "E:/Escape/_AI/runs/$runId/analysis.json"
$mutex = [System.Threading.Mutex]::new($false, "Global\EscapeAIChampionFirstPlayer")
$ownsMutex = $false

try {
    $ownsMutex = $mutex.WaitOne(0)
    if (-not $ownsMutex) {
        throw "another champion first-player diagnostic is already running"
    }
    New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
    $startedAt = Get-Date -Format "yyyyMMdd-HHmmss"
    $logPath = Join-Path $logRoot "champion-first-player-$startedAt.log"
    Start-Transcript -Path $logPath -Append | Out-Null

    Push-Location $repoRoot
    try {
        if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
            throw "Escape AI environment is missing: $runner"
        }
        $dirty = git status --porcelain
        if ($dirty) {
            throw "formal champion first-player diagnostic requires a clean worktree"
        }
        $commit = git rev-parse HEAD
        Write-Host "Starting or resuming first-player diagnostic from commit $commit"
        & $runner generate-research-games --config $config
        if ($LASTEXITCODE -ne 0) {
            throw "first-player game generation failed with exit code $LASTEXITCODE"
        }
        & $runner analyze-first-player --input $games --output $analysis
        if ($LASTEXITCODE -ne 0) {
            throw "first-player analysis failed with exit code $LASTEXITCODE"
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
