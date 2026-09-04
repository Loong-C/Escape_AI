$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactRoot = "G:\Escape\_AI"
$logRoot = Join-Path $artifactRoot "runs\formal-lineages"
$python = Join-Path $repoRoot ".venv\Scripts\escape-ai.exe"
$mutex = [System.Threading.Mutex]::new($false, "Global\EscapeAIFormalLineages")
$ownsMutex = $false

try {
    $ownsMutex = $mutex.WaitOne(0)
    if (-not $ownsMutex) {
        throw "another formal lineage launcher is already running"
    }
    New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
    $startedAt = Get-Date -Format "yyyyMMdd-HHmmss"
    $logPath = Join-Path $logRoot "lineages-$startedAt.log"
    Start-Transcript -Path $logPath -Append | Out-Null

    Push-Location $repoRoot
    try {
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
            throw "Escape AI environment is missing: $python"
        }
        $dirty = git status --porcelain
        if ($dirty) {
            throw "formal lineages require a clean worktree"
        }
        $commit = git rev-parse HEAD
        Write-Host "Starting formal lineages from commit $commit"

        $configs = @(
            "configs\lineages\lineage-a-17x17-v1.yaml",
            "configs\lineages\lineage-b-17x17-v1.yaml",
            "configs\lineages\lineage-c-17x17-v1.yaml"
        )
        foreach ($config in $configs) {
            Write-Host "Running or resuming $config"
            & $python run-lineage --config $config
            if ($LASTEXITCODE -ne 0) {
                throw "lineage failed with exit code ${LASTEXITCODE}: $config"
            }
        }

        $completion = @{
            completed_at = (Get-Date).ToUniversalTime().ToString("o")
            git_commit = $commit
            configs = $configs
        } | ConvertTo-Json
        Set-Content -LiteralPath (Join-Path $logRoot "complete.json") -Value $completion
        Write-Host "All formal lineages completed."
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
