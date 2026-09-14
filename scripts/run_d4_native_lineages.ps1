$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactRoot = "E:\Escape\_AI"
$logRoot = Join-Path $artifactRoot "runs\d4-native-lineages"
$runner = Join-Path $repoRoot ".venv\Scripts\escape-ai.exe"
$mutex = [System.Threading.Mutex]::new($false, "Global\EscapeAID4NativeLineages")
$ownsMutex = $false

try {
    $ownsMutex = $mutex.WaitOne(0)
    if (-not $ownsMutex) {
        throw "another D4-native lineage launcher is already running"
    }
    New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
    $startedAt = Get-Date -Format "yyyyMMdd-HHmmss"
    $logPath = Join-Path $logRoot "d4-native-lineages-$startedAt.log"
    Start-Transcript -Path $logPath -Append | Out-Null

    Push-Location $repoRoot
    try {
        if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
            throw "Escape AI environment is missing: $runner"
        }
        $dirty = git status --porcelain
        if ($dirty) {
            throw "formal D4-native lineages require a clean worktree"
        }
        $commit = git rev-parse HEAD
        Write-Host "Starting or resuming D4-native lineages from commit $commit"

        $configs = @(
            "configs\lineages\lineage-c-d4-finetune-17x17-v1.yaml",
            "configs\lineages\lineage-d-d4-native-17x17-v1.yaml"
        )
        foreach ($config in $configs) {
            Write-Host "Running or resuming $config"
            & $runner run-lineage --config $config
            if ($LASTEXITCODE -ne 0) {
                throw "D4-native lineage failed with exit code ${LASTEXITCODE}: $config"
            }
        }

        $completion = @{
            completed_at = (Get-Date).ToUniversalTime().ToString("o")
            git_commit = $commit
            configs = $configs
        } | ConvertTo-Json
        Set-Content -LiteralPath (Join-Path $logRoot "complete.json") -Value $completion
        Write-Host "All D4-native lineages completed."
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
