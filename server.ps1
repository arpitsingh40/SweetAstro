# SweetAstro server manager for Windows PowerShell.
# Usage:
#   .\server.ps1 start        start in background (hidden), logs to data\logs\
#   .\server.ps1 stop         stop the background server
#   .\server.ps1 restart      stop + start
#   .\server.ps1 status       show process state and API health
#   .\server.ps1 logs         tail the server logs
#   .\server.ps1 check        run startup preflight checks only (no server)
#   .\server.ps1 register     auto-start the server at Windows logon
#   .\server.ps1 unregister   remove the logon auto-start
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "check", "register", "unregister")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $Root "data\server.pid"
$LogDir = Join-Path $Root "data\logs"
$OutLog = Join-Path $LogDir "server.log"
$ErrLog = Join-Path $LogDir "server.err.log"
$TaskName = "SweetAstroServer"

# Port/host: environment wins, else .env, else defaults
$HostAddr = "127.0.0.1"
$Port = 8088
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*SWEETASTRO_HOST\s*=\s*(.+)$') { $HostAddr = $Matches[1].Trim() }
        if ($_ -match '^\s*SWEETASTRO_PORT\s*=\s*(.+)$') { $Port = [int]$Matches[1].Trim() }
    }
}
if ($env:SWEETASTRO_HOST) { $HostAddr = $env:SWEETASTRO_HOST }
if ($env:SWEETASTRO_PORT) { $Port = [int]$env:SWEETASTRO_PORT }
$HealthUrl = "http://127.0.0.1:$Port/api/health"

function Get-ServerProcess {
    if (-not (Test-Path $PidFile)) { return $null }
    $serverPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if (-not $serverPid) { return $null }
    return Get-Process -Id $serverPid -ErrorAction SilentlyContinue
}

function Test-Health {
    try {
        $r = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 5
        return $r
    } catch {
        return $null
    }
}

function Start-Server {
    $proc = Get-ServerProcess
    if ($proc) {
        Write-Output "Already running (PID $($proc.Id))."
        return
    }
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    $script = Join-Path $Root "serve.py"
    $extraArgs = @()
    if ($env:SWEETASTRO_RELOAD) { $extraArgs += "--reload" }
    $started = Start-Process -FilePath python -ArgumentList (@("`"$script`"") + $extraArgs) `
        -WorkingDirectory $Root -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
    Set-Content -LiteralPath $PidFile -Value $started.Id
    Write-Output "Starting SweetAstro (PID $($started.Id)) ..."
    foreach ($i in 1..40) {
        Start-Sleep -Milliseconds 250
        $health = Test-Health
        if ($health) {
            if ($health.chat_ready -ne $true) {
                Write-Output "ABORT: server started but chat is NOT ready (DeepSeek key missing or invalid). Stopping."
                Stop-Process -Id $started.Id -Force -ErrorAction SilentlyContinue
                Remove-Item $PidFile -ErrorAction SilentlyContinue
                return
            }
            Write-Output "Up: http://127.0.0.1:$Port  (engine: $($health.ephemeris_engine), chat READY)"
            return
        }
        if ($started.HasExited) {
            Write-Output "Server exited during startup. Last log lines:"
            if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 20 }
            Remove-Item $PidFile -ErrorAction SilentlyContinue
            return
        }
    }
    Write-Output "Server process is running but health check did not respond yet - see .\server.ps1 logs"
}

function Stop-Server {
    $proc = Get-ServerProcess
    if (-not $proc) {
        Write-Output "Not running."
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        return
    }
    Stop-Process -Id $proc.Id -Force
    Remove-Item $PidFile -ErrorAction SilentlyContinue
    Write-Output "Stopped (PID $($proc.Id))."
}

function Show-Status {
    $proc = Get-ServerProcess
    $health = Test-Health
    if ($proc) { Write-Output "Process : running (PID $($proc.Id))" } else { Write-Output "Process : stopped" }
    if ($health) {
        Write-Output "API     : healthy at http://127.0.0.1:$Port"
        Write-Output "Engine  : $($health.ephemeris_engine) - $($health.ephemeris_data)"
        $ready = if ($health.chat_ready -eq $true) { "READY" } else { "NOT READY (DeepSeek key missing)" }
        Write-Output "Chat    : $ready - model $($health.chat_model)"
    } else {
        Write-Output "API     : not responding"
    }
}

function Show-Logs {
    Write-Output "=== server.err.log (application + access) ==="
    if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 40 } else { Write-Output "(none)" }
    Write-Output ""
    Write-Output "=== server.log (banner + access) ==="
    if (Test-Path $OutLog) { Get-Content $OutLog -Tail 20 } else { Write-Output "(none)" }
}

function Register-Autostart {
    $script = (Resolve-Path $MyInvocation.MyCommand.Path).Path
    $cmd = "powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`" start"
    schtasks /Create /SC ONLOGON /TN $TaskName /TR $cmd /F | Out-Null
    Write-Output "Registered logon autostart task '$TaskName'."
}

function Unregister-Autostart {
    schtasks /Delete /TN $TaskName /F 2>$null | Out-Null
    Write-Output "Removed logon autostart task '$TaskName' (if it existed)."
}

switch ($Action) {
    "start" { Start-Server }
    "stop" { Stop-Server }
    "restart" { Stop-Server; Start-Sleep -Milliseconds 400; Start-Server }
    "status" { Show-Status }
    "logs" { Show-Logs }
    "check" { & python (Join-Path $Root "serve.py") --check; exit $LASTEXITCODE }
    "register" { Register-Autostart }
    "unregister" { Unregister-Autostart }
}
