$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactRoot = "E:\Escape\_AI"
$logRoot = Join-Path $artifactRoot "runs\canonical-d4-lineage"
$runner = Join-Path $repoRoot ".venv\Scripts\escape-ai.exe"
$mutex = [System.Threading.Mutex]::new($false, "Global\EscapeAICanonicalD4Lineage")
$ownsMutex = $false

try {
    $ownsMutex = $mutex.WaitOne(0)
    if (-not $ownsMutex) {
        throw "another canonical-D4 lineage launcher is already running"
    }
    New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
    $startedAt = Get-Date -Format "yyyyMMdd-HHmmss"
    $logPath = Join-Path $logRoot "canonical-d4-lineage-$startedAt.log"
    Start-Transcript -Path $logPath -Append | Out-Null

    Push-Location $repoRoot
    try {
        if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
            throw "Escape AI environment is missing: $runner"
        }
        $dirty = git status --porcelain
        if ($dirty) {
            throw "formal canonical-D4 lineage requires a clean worktree"
        }
        $commit = git rev-parse HEAD
        $config = "configs\lineages\lineage-d-d4-canonical-17x17-v2.yaml"
        Write-Host "Starting or resuming canonical-D4 lineage from commit $commit"
        & $runner run-lineage --config $config
        if ($LASTEXITCODE -ne 0) {
            throw "canonical-D4 lineage failed with exit code $LASTEXITCODE"
        }

        @{
            completed_at = (Get-Date).ToUniversalTime().ToString("o")
            git_commit = $commit
            config = $config
        } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logRoot "complete.json")
        Write-Host "Canonical-D4 lineage completed."
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
