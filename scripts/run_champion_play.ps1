param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8765,
    [string]$Device = "cuda"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$EscapeAi = Join-Path $RepoRoot ".venv\Scripts\escape-ai.exe"
$Checkpoint = "E:\Escape\_AI\checkpoints\lineage-c-17x17-v1\generation-0199.pt"
$Games = "E:\Escape\_AI\games\champion-analysis-17x17-v1"
$ExpectedSha256 = "0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3"

if (-not (Test-Path -LiteralPath $EscapeAi)) {
    throw "Escape AI executable not found: $EscapeAi"
}
if (-not (Test-Path -LiteralPath $Checkpoint)) {
    throw "Champion checkpoint not found: $Checkpoint"
}
if (-not (Test-Path -LiteralPath $Games)) {
    throw "Research games not found: $Games"
}

Push-Location (Join-Path $RepoRoot "viewer")
try {
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "Viewer build failed" }
}
finally {
    Pop-Location
}

& $EscapeAi serve-play `
    --games $Games `
    --checkpoint $Checkpoint `
    --checkpoint-sha256 $ExpectedSha256 `
    --device $Device `
    --simulations 512 `
    --host $BindHost `
    --port $Port
