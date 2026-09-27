param(
    [Parameter(Mandatory = $true)][string]$RuntimeConfig
)

$ErrorActionPreference = "Stop"
$Settings = Get-Content -LiteralPath $RuntimeConfig -Raw | ConvertFrom-Json
$Mutex = [System.Threading.Mutex]::new($false, "Local\EscapeChampionProduction")
if (-not $Mutex.WaitOne(0)) { exit 0 }
$PythonProcess = $null
$TunnelProcess = $null
try {
    foreach ($Line in Get-Content -LiteralPath $Settings.credentialFile) {
        if ($Line.StartsWith("ESCAPE_INFERENCE_KEY=")) {
            $env:ESCAPE_INFERENCE_KEY = $Line.Substring("ESCAPE_INFERENCE_KEY=".Length)
        }
    }
    if ($env:ESCAPE_INFERENCE_KEY.Length -lt 32) { throw "Missing inference credential" }
    $env:ESCAPE_DEVICE = "cuda"
    $env:ESCAPE_CHAMPION_CHECKPOINT = $Settings.checkpoint
    $env:PYTHONPATH = Join-Path $Settings.sourceDirectory "src"
    $env:PYTHONDONTWRITEBYTECODE = "1"
    New-Item -ItemType Directory -Path $Settings.logDirectory -Force | Out-Null

    while ($true) {
        if ($null -eq $PythonProcess -or $PythonProcess.HasExited) {
            $PythonProcess = Start-Process -FilePath $Settings.python -ArgumentList @(
                "-m", "uvicorn", "escape_ai.play.production:app_factory", "--factory",
                "--host", "127.0.0.1", "--port", "18765", "--workers", "1",
                "--limit-concurrency", "8", "--timeout-keep-alive", "5", "--no-access-log"
            ) -WorkingDirectory $Settings.sourceDirectory -WindowStyle Hidden -PassThru `
                -RedirectStandardOutput (Join-Path $Settings.logDirectory "inference.stdout.log") `
                -RedirectStandardError (Join-Path $Settings.logDirectory "inference.stderr.log")
        }
        $Ready = $false
        try {
            $Health = Invoke-RestMethod -Uri "http://127.0.0.1:18765/health" -TimeoutSec 2
            $Ready = ($Health.model.checkpoint_sha256 -eq `
                "0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3") `
                -and ($Health.model.device -eq "cuda") `
                -and ($Health.model.simulations -eq 512)
        }
        catch { $Ready = $false }
        if ($Ready -and ($null -eq $TunnelProcess -or $TunnelProcess.HasExited)) {
            $TunnelProcess = Start-Process -FilePath $Settings.ssh -ArgumentList @(
                "-NT", "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
                "-o", "StrictHostKeyChecking=yes", "-o", "ExitOnForwardFailure=yes",
                "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15",
                "-o", "ServerAliveCountMax=3", "-i", $Settings.tunnelKey,
                "-R", "127.0.0.1:18765:127.0.0.1:18765",
                "escape-inference-tunnel@139.59.239.152"
            ) -WindowStyle Hidden -PassThru `
                -RedirectStandardOutput (Join-Path $Settings.logDirectory "tunnel.stdout.log") `
                -RedirectStandardError (Join-Path $Settings.logDirectory "tunnel.stderr.log")
        }
        Start-Sleep -Seconds 5
    }
}
finally {
    foreach ($Child in @($TunnelProcess, $PythonProcess)) {
        if ($null -ne $Child -and -not $Child.HasExited) { $Child.Kill() }
    }
    $Mutex.ReleaseMutex()
    $Mutex.Dispose()
}
