$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactRoot = "E:\Escape\_AI"
$logRoot = Join-Path $artifactRoot "runs\champion-analysis-launcher"
$runner = Join-Path $repoRoot ".venv\Scripts\escape-ai.exe"
$config = "configs\games\champion-analysis-17x17-v1.yaml"
$gameRoot = Join-Path $artifactRoot "games\champion-analysis-17x17-v1"
$analysis = Join-Path $artifactRoot "runs\champion-analysis-17x17-v1\analysis.json"
$mutex = [System.Threading.Mutex]::new($false, "Global\EscapeAIChampionAnalysis")
$ownsMutex = $false

try {
    $ownsMutex = $mutex.WaitOne(0)
    if (-not $ownsMutex) {
        throw "another champion analysis launcher is already running"
    }
    New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
    $startedAt = Get-Date -Format "yyyyMMdd-HHmmss"
    $logPath = Join-Path $logRoot "champion-analysis-$startedAt.log"
    Start-Transcript -Path $logPath -Append | Out-Null

    Push-Location $repoRoot
    try {
        if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
            throw "Escape AI environment is missing: $runner"
        }
        $dirty = git status --porcelain
        if ($dirty) {
            throw "formal champion analysis requires a clean worktree"
        }
        $commit = git rev-parse HEAD
        Write-Host "Starting or resuming champion analysis from commit $commit"
        & $runner generate-research-games --config $config
        if ($LASTEXITCODE -ne 0) {
            throw "champion analysis generation failed with exit code $LASTEXITCODE"
        }
        & $runner analyze-games --input $gameRoot --output $analysis
        if ($LASTEXITCODE -ne 0) {
            throw "champion analysis summarization failed with exit code $LASTEXITCODE"
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
