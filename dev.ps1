# SweetAstro developer workflow.
#
# Always runs from the project directory, so pytest can never scan or run
# tests from sibling projects (Smartdecision, SolarDeals, etc.).
#
# Hang protection is enforced at two levels:
#   1. pytest-timeout kills any single test that exceeds 60 s (pytest.ini)
#   2. this script watchdog-kills the whole run if it exceeds -RunTimeoutSeconds
#
# Usage:
#   .\dev.ps1 test           full suite (~7 s)
#   .\dev.ps1 test-fast      skip the 'slow' marker (~4 s)
#   .\dev.ps1 test-quick     last-failed only, stop at first failure (fast loop)
#   .\dev.ps1 test-one -Path tests/test_chat.py   single file (fastest loop)
#   .\dev.ps1 restart        server restart only (~2 s) — backend changes
#   .\dev.ps1 dev            fast dev server: auto-reload + skip network preflight
#   .\dev.ps1 verify         startup preflight checks (aborts on failure)
#   .\dev.ps1 deploy         preflight -> web build -> fast tests -> restart -> health
#   .\dev.ps1 deploy -SkipTests   preflight -> restart -> health (no test run)
#   .\dev.ps1 deploy -SkipTests -SkipNet   offline/fast ship (skips all network checks)
#   .\dev.ps1 accuracy       pre-registered accuracy backtest (writes reports/)
#   .\dev.ps1 ui-install     install frontend toolchain (frontend/npm install)
#   .\dev.ps1 ui-dev         Vite dev server with HMR (proxies /api to :8088)
#   .\dev.ps1 ui-watch       rebuild src/api/static/app on every save (no restart needed)
#   .\dev.ps1 ui-build       typecheck + build the React app (quiet output)
#   .\dev.ps1 ui-typecheck   TypeScript check only
#   .\dev.ps1 dev-all        backend (auto-reload) + Vite HMR window in one command
#
# Fast dev loop (recommended):
#   1. .\dev.ps1 dev-all      -> backend reloads on Python saves; Vite HMR window opens
#   2. UI edits: change frontend/src -> instant HMR at http://127.0.0.1:5174/static/app/
#   3. Ship: .\dev.ps1 deploy (web build is skipped automatically when nothing changed)
param(
    [Parameter(Position = 0)]
    [ValidateSet("test", "test-fast", "test-quick", "test-one", "restart", "dev", "verify", "deploy", "accuracy",
        "ui-install", "ui-dev", "ui-watch", "ui-build", "ui-typecheck", "dev-all")]
    [string]$Action = "test",
    [string]$Path = "",
    [switch]$SkipTests,
    [switch]$SkipNet,
    [int]$RunTimeoutSeconds = 300
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root

# Network preflight bypass (same as $env:SWEETASTRO_SKIP_NET_CHECK=1).
if ($SkipNet) { $env:SWEETASTRO_SKIP_NET_CHECK = "1" }

function Invoke-Pytest([string[]]$TestArgs, [int]$TimeoutSeconds = $RunTimeoutSeconds) {
    $quoted = ($TestArgs | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '

    # Direct .NET Process: Start-Process -PassThru does not reliably expose
    # ExitCode when output is redirected (returns $null on PS 5.1), which made
    # deploy abort with "tests failed" even on green runs.
    # Prefer the pytest console script when present (skips the `python -m` wrapper).
    $pytestExe = Join-Path $env:APPDATA "Python\Python314\Scripts\pytest.exe"
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    if (Test-Path $pytestExe) {
        $psi.FileName = $pytestExe
        $psi.Arguments = $quoted
    } else {
        $psi.FileName = "python"
        $psi.Arguments = '-m pytest ' + $quoted
    }
    $psi.WorkingDirectory = $Root
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    [void]$proc.Start()
    $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
    $stderrTask = $proc.StandardError.ReadToEndAsync()
    $finished = $proc.WaitForExit($TimeoutSeconds * 1000)

    if (-not $finished) {
        & taskkill /PID $proc.Id /T /F 2>$null | Out-Null
        Start-Sleep -Milliseconds 400
        if ($stdoutTask.Wait(2000)) { Write-Host $stdoutTask.Result }
        Write-Host "TEST RUN KILLED by watchdog after ${TimeoutSeconds}s (process tree terminated)."
        return 124
    }

    $stdout = ""
    $stderr = ""
    try { $stdout = $stdoutTask.Result } catch { }
    try { $stderr = $stderrTask.Result } catch { }
    if ($stdout) { Write-Host $stdout }
    if ($stderr.Trim()) { Write-Host $stderr }
    return $proc.ExitCode
}

function Invoke-Verify {
    & python serve.py --check | Write-Host
    return $LASTEXITCODE
}

switch ($Action) {
    "test" {
        $code = Invoke-Pytest @("-q")
        [Environment]::Exit($code)
    }
    "test-fast" {
        $code = Invoke-Pytest @("-q", "-m", "not slow")
        [Environment]::Exit($code)
    }
    "test-quick" {
        $code = Invoke-Pytest @("-q", "-x", "--lf", "-m", "not slow")
        [Environment]::Exit($code)
    }
    "test-one" {
        if (-not $Path -or -not (Test-Path -LiteralPath $Path)) {
            Write-Output "Usage: .\dev.ps1 test-one -Path tests/test_chat.py"
            [Environment]::Exit(2)
        }
        $code = Invoke-Pytest @("-q", "-x", $Path)
        [Environment]::Exit($code)
    }
    "restart" {
        & (Join-Path $Root "server.ps1") restart
        [Environment]::Exit($LASTEXITCODE)
    }
    "dev" {
        Write-Output "Fast dev server: auto-reload ON, network preflight OFF"
        $env:SWEETASTRO_RELOAD = "1"
        $env:SWEETASTRO_SKIP_NET_CHECK = "1"
        & (Join-Path $Root "server.ps1") restart
        Write-Output "Backend edits now auto-reload. UI edits need no restart (just refresh)."
        [Environment]::Exit($LASTEXITCODE)
    }
    "verify" {
        [Environment]::Exit((Invoke-Verify))
    }
    "deploy" {
        Write-Output "[1/4] Preflight checks"
        $verify = Invoke-Verify
        if ($verify -ne 0) {
            Write-Output "DEPLOY ABORTED: preflight failed."
            [Environment]::Exit($verify)
        }
        Write-Output "[2/4] Building web app"
        $frontend = Join-Path $Root "frontend"
        $distIndex = Join-Path $Root "src\api\static\app\index.html"
        $needsBuild = $true
        if ((Test-Path $distIndex) -and (Test-Path (Join-Path $frontend "src"))) {
            $watchPaths = @(
                (Join-Path $frontend "src"),
                (Join-Path $frontend "index.html"),
                (Join-Path $frontend "package.json"),
                (Join-Path $frontend "vite.config.ts"),
                (Join-Path $frontend "tsconfig.json")
            ) | Where-Object { Test-Path $_ }
            $newest = Get-ChildItem -Path $watchPaths -Recurse -File -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTime -Descending | Select-Object -First 1
            if ($newest -and $newest.LastWriteTime -le (Get-Item $distIndex).LastWriteTime) {
                $needsBuild = $false
            }
        }
        if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
            Write-Output "  (frontend toolchain not installed - run .\dev.ps1 ui-install; serving last build)"
        } elseif ($needsBuild) {
            & npm --prefix $frontend run build:quiet
            if ($LASTEXITCODE -ne 0) {
                Write-Output "DEPLOY ABORTED: web app build failed."
                [Environment]::Exit($LASTEXITCODE)
            }
        } else {
            Write-Output "  (web app up to date - skipped)"
        }
        if (-not $SkipTests) {
            Write-Output "[3/4] Fast test suite"
            $tests = Invoke-Pytest @("-q", "-m", "not slow")
            if ($tests -ne 0) {
                Write-Output "DEPLOY ABORTED: tests failed."
                [Environment]::Exit($tests)
            }
        } else {
            Write-Output "[3/4] Tests skipped (-SkipTests)"
        }
        Write-Output "[4/4] Restarting server"
        & (Join-Path $Root "server.ps1") restart
        $health = $null
        foreach ($i in 1..15) {
            Start-Sleep -Milliseconds 500
            try {
                $health = Invoke-RestMethod -Uri "http://127.0.0.1:8088/api/health" -TimeoutSec 3
                if ($health.status -eq "healthy") { break }
            } catch { }
        }
        if ($health -and $health.status -eq "healthy") {
            Write-Output "DEPLOY OK: chat_ready=$($health.chat_ready), engine=$($health.ephemeris_engine), app=/app"
            [Environment]::Exit(0)
        }
        Write-Output "DEPLOY FAILED: server did not become healthy."
        [Environment]::Exit(1)
    }
    "accuracy" {
        & python accuracy_backtest.py | Write-Host
        [Environment]::Exit($LASTEXITCODE)
    }
    "ui-install" {
        & npm --prefix (Join-Path $Root "frontend") install
        [Environment]::Exit($LASTEXITCODE)
    }
    "ui-dev" {
        & npm --prefix (Join-Path $Root "frontend") run dev
        [Environment]::Exit($LASTEXITCODE)
    }
    "ui-watch" {
        Write-Output "Rebuilding src/api/static/app on every save (Ctrl+C to stop)."
        Write-Output "The running server serves the new build at http://127.0.0.1:8088/app - just refresh."
        & npm --prefix (Join-Path $Root "frontend") run watch
        [Environment]::Exit($LASTEXITCODE)
    }
    "ui-build" {
        & npm --prefix (Join-Path $Root "frontend") run build:quiet
        [Environment]::Exit($LASTEXITCODE)
    }
    "ui-typecheck" {
        & npm --prefix (Join-Path $Root "frontend") run typecheck
        [Environment]::Exit($LASTEXITCODE)
    }
    "dev-all" {
        Write-Output "Starting backend (auto-reload) + Vite HMR window..."
        $env:SWEETASTRO_RELOAD = "1"
        $env:SWEETASTRO_SKIP_NET_CHECK = "1"
        & (Join-Path $Root "server.ps1") restart
        if ($LASTEXITCODE -ne 0) { [Environment]::Exit($LASTEXITCODE) }
        $frontendPath = Join-Path $Root "frontend"
        Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$frontendPath`" && npm run dev"
        Write-Output ""
        Write-Output "Backend + API : http://127.0.0.1:8088  (reloads on Python saves)"
        Write-Output "Dev app (HMR) : http://localhost:5174/static/app/  <- open this while developing"
        Write-Output "Production app: http://127.0.0.1:8088/app  (updated by ui-build/ui-watch/deploy)"
        Write-Output ""
        Write-Output "A new window is running Vite; close it (or Ctrl+C) to stop HMR."
        [Environment]::Exit(0)
    }
}
