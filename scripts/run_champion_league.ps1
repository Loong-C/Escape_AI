$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactRoot = "E:\Escape\_AI"
$logRoot = Join-Path $artifactRoot "runs\champion-leagues"
$runner = Join-Path $repoRoot ".venv\Scripts\escape-ai.exe"
$mutex = [System.Threading.Mutex]::new($false, "Global\EscapeAIChampionLeague")
$ownsMutex = $false

try {
    $ownsMutex = $mutex.WaitOne(0)
    if (-not $ownsMutex) {
        throw "another champion league launcher is already running"
    }
    New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
    $startedAt = Get-Date -Format "yyyyMMdd-HHmmss"
    $logPath = Join-Path $logRoot "champion-league-$startedAt.log"
    Start-Transcript -Path $logPath -Append | Out-Null

    Push-Location $repoRoot
    try {
        if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
            throw "Escape AI environment is missing: $runner"
        }
        $dirty = git status --porcelain
        if ($dirty) {
            throw "formal champion league requires a clean worktree"
        }
        $commit = git rev-parse HEAD
        Write-Host "Starting or resuming champion league from commit $commit"
        & $runner run-champion-league --config configs\leagues\champion-17x17-v1.yaml
        if ($LASTEXITCODE -ne 0) {
            throw "champion league failed with exit code $LASTEXITCODE"
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
