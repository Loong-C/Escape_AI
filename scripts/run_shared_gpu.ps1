param([Parameter(Mandatory = $true)][string]$RuntimeConfig)

$ErrorActionPreference = 'Stop'
$Settings = Get-Content -LiteralPath $RuntimeConfig -Raw | ConvertFrom-Json
$Mutex = [System.Threading.Mutex]::new($false, 'Local\LinkukaiProductionGPU')
if (-not $Mutex.WaitOne(0)) { exit 0 }
$EscapeProcess = $null
$VocaProcess = $null
$TunnelProcess = $null
$StateFile = Join-Path (Split-Path -Parent $RuntimeConfig) 'gpu-processes.json'

function Write-RuntimeEvent([string]$Message) {
    Add-Content -LiteralPath (Join-Path $Settings.logDirectory 'supervisor.log') `
        -Value "$(Get-Date -Format o) $Message" -Encoding UTF8
}

function Restore-Process($Record, [string]$ExpectedName) {
    if ($null -eq $Record) { return $null }
    try {
        $Existing = Get-Process -Id $Record.id -ErrorAction Stop
        $Created = $Existing.StartTime.ToUniversalTime().Ticks.ToString()
        if ($Created -eq $Record.createdUtcTicks -and $Existing.ProcessName -eq $ExpectedName) {
            Write-RuntimeEvent "Adopted $ExpectedName process $($Existing.Id)"
            return $Existing
        }
    }
    catch { return $null }
    return $null
}

function Save-ProcessState {
    $State = @{ runtimeConfig = [System.IO.Path]::GetFullPath($RuntimeConfig) }
    foreach ($Entry in (@{ escape = $EscapeProcess; vocap = $VocaProcess; tunnel = $TunnelProcess }).GetEnumerator()) {
        $Child = $Entry.Value
        try {
            if ($null -ne $Child -and -not $Child.HasExited) {
                $State[$Entry.Key] = @{ id = $Child.Id; createdUtcTicks = $Child.StartTime.ToUniversalTime().Ticks.ToString() }
            }
        }
        catch { continue }
    }
    $Temporary = "$StateFile.next"
    $State | ConvertTo-Json | Set-Content -LiteralPath $Temporary -Encoding UTF8
    if (Test-Path -LiteralPath $StateFile) {
        # Windows PowerShell 5.1 binds a null string to an empty path here.
        [System.IO.File]::Replace($Temporary, $StateFile, "$StateFile.previous")
    } else {
        [System.IO.File]::Move($Temporary, $StateFile)
    }
}

function Start-Backend($Python, $Source, $App, $Port, $Name) {
    $env:PYTHONPATH = Join-Path $Source 'src'
    Start-Process -FilePath $Python -ArgumentList @(
        '-m', 'uvicorn', $App, '--factory', '--host', '127.0.0.1', '--port', $Port,
        '--workers', '1', '--limit-concurrency', '12', '--timeout-keep-alive', '5', '--no-access-log'
    ) -WorkingDirectory $Source -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $Settings.logDirectory "$Name.stdout.log") `
        -RedirectStandardError (Join-Path $Settings.logDirectory "$Name.stderr.log")
}

try {
    foreach ($Line in Get-Content -LiteralPath $Settings.credentialFile) {
        if ($Line.StartsWith('ESCAPE_INFERENCE_KEY=')) {
            $env:ESCAPE_INFERENCE_KEY = $Line.Substring('ESCAPE_INFERENCE_KEY='.Length)
        }
    }
    foreach ($Line in Get-Content -LiteralPath $Settings.vocaCredentialFile) {
        if ($Line.StartsWith('VOCAP_INFERENCE_KEY=')) {
            $env:VOCAP_INFERENCE_KEY = $Line.Substring('VOCAP_INFERENCE_KEY='.Length)
        }
    }
    if ($env:ESCAPE_INFERENCE_KEY.Length -lt 32 -or $env:VOCAP_INFERENCE_KEY.Length -lt 32) {
        throw 'Missing proxy credentials'
    }
    $env:ESCAPE_DEVICE = 'cuda'
    $env:ESCAPE_CHAMPION_CHECKPOINT = $Settings.checkpoint
    $env:PYTHONUTF8 = '1'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:HF_HOME = $Settings.hfHome
    $env:HF_HUB_OFFLINE = '1'
    $env:OMP_NUM_THREADS = '2'
    $env:MKL_NUM_THREADS = '2'
    New-Item -ItemType Directory -Path $Settings.logDirectory -Force | Out-Null
    Write-RuntimeEvent "Supervisor started: PID $PID"
    if (Test-Path -LiteralPath $StateFile) {
        $Saved = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
        if ($Saved.runtimeConfig -ne [System.IO.Path]::GetFullPath($RuntimeConfig)) {
            throw 'Saved processes belong to a different runtime configuration'
        }
        $EscapeProcess = Restore-Process $Saved.escape 'python'
        $VocaProcess = Restore-Process $Saved.vocap 'python'
        $TunnelProcess = Restore-Process $Saved.tunnel 'ssh'
    }
    while ($true) {
        if ($null -eq $EscapeProcess -or $EscapeProcess.HasExited) {
            $EscapeProcess = Start-Backend $Settings.python $Settings.sourceDirectory 'escape_ai.play.production:app_factory' '18765' 'escape'
            Save-ProcessState
            Write-RuntimeEvent "Started Escape process $($EscapeProcess.Id)"
        }
        if ($null -eq $VocaProcess -or $VocaProcess.HasExited) {
            $VocaProcess = Start-Backend $Settings.vocaPython $Settings.vocaSourceDirectory 'vocaptest.api.production:app_factory' '18766' 'vocap'
            Save-ProcessState
            Write-RuntimeEvent "Started VocaPTest process $($VocaProcess.Id)"
        }
        # One SSH transport with two independently usable loopback forwards.
        # Never make Escape availability depend on VocaPTest warm-up (or vice versa).
        if ($null -eq $TunnelProcess -or $TunnelProcess.HasExited) {
            $TunnelProcess = Start-Process -FilePath $Settings.ssh -ArgumentList @(
                '-NT', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
                '-o', 'StrictHostKeyChecking=yes', '-o', 'ExitOnForwardFailure=yes',
                '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=5',
                '-o', 'ServerAliveCountMax=2', '-i', $Settings.tunnelKey,
                '-R', '127.0.0.1:18765:127.0.0.1:18765',
                '-R', '127.0.0.1:18766:127.0.0.1:18766',
                'escape-inference-tunnel@139.59.239.152'
            ) -WindowStyle Hidden -PassThru `
                -RedirectStandardOutput (Join-Path $Settings.logDirectory 'tunnel.stdout.log') `
                -RedirectStandardError (Join-Path $Settings.logDirectory 'tunnel.stderr.log')
            Save-ProcessState
            Write-RuntimeEvent "Started shared SSH process $($TunnelProcess.Id)"
        }
        Start-Sleep -Seconds 5
    }
}
finally {
    foreach ($Child in @($TunnelProcess, $EscapeProcess, $VocaProcess)) {
        if ($null -ne $Child -and -not $Child.HasExited) {
            # A Windows virtualenv Python launcher has a child Python process.
            # Terminate the owned tree so a normal stop cannot leave listeners behind.
            & taskkill.exe /PID $Child.Id /T /F | Out-Null
        }
    }
    $Mutex.ReleaseMutex()
    $Mutex.Dispose()
}
