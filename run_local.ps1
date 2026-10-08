<#
.SYNOPSIS
    AI Solution Builder - Local Runner for Windows PowerShell.
    Runs the entire application stack locally with ZERO Docker bloat on your C: drive,
    or optionally with lightweight Docker infra (Postgres+Redis only) or full Docker.

.DESCRIPTION
    Usage:
      .\run_local.ps1              (DEFAULT) Run entire stack natively on host (0 Docker bloat)
      .\run_local.ps1 -Detach      Run native stack in background
      .\run_local.ps1 -Infra       Lightweight mode: run Postgres+Redis in Docker, app native
      .\run_local.ps1 -Docker      Run entire stack in Docker (no forced rebuilds)
      .\run_local.ps1 -DockerBuild Run full Docker stack with image rebuilds
      .\run_local.ps1 -Stop        Stop all running services (native and/or Docker)
      .\run_local.ps1 -Status      Show health, process, and port status
      .\run_local.ps1 -Logs [svc]  Tail service logs (backend, frontend, opencode, worker, all)
      .\run_local.ps1 -Prune       Reclaim GBs on C: drive (clean Docker cache & unused images)
      .\run_local.ps1 -Down        Stop services and remove Docker volumes
#>

param(
    [Parameter(Position=0)]
    [string]$Command = "up",

    [switch]$Detach,
    [switch]$Infra,
    [switch]$Docker,
    [switch]$DockerBuild,
    [switch]$Stop,
    [switch]$Status,
    [switch]$Prune,
    [switch]$Down,
    [string]$Logs = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

$BackendUrl  = "http://127.0.0.1:8000"
$FrontendUrl = "http://127.0.0.1:3000"
$SidecarUrl  = "http://127.0.0.1:4096"
$HealthTimeout = 90

$LogDir  = Join-Path $ScriptDir ".data\logs"
$PidDir  = Join-Path $ScriptDir ".data\pids"
$DataDir = Join-Path $ScriptDir ".data"

foreach ($dir in @($LogDir, $PidDir, (Join-Path $DataDir "mvp_builds"), (Join-Path $DataDir "uploads"), (Join-Path $DataDir "exports"))) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

function Write-Step([string]$msg) {
    Write-Host "`n==> $msg" -ForegroundColor Cyan
}

function Write-Success([string]$msg) {
    Write-Host "    [OK] $msg" -ForegroundColor Green
}

function Write-Warn([string]$msg) {
    Write-Host "WARNING: $msg" -ForegroundColor Yellow
}

function Write-Err([string]$msg) {
    Write-Host "ERROR: $msg" -ForegroundColor Red
}

function Test-PortListening([int]$Port) {
    try {
        $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        return ($null -ne $c)
    } catch {
        return $false
    }
}

function Test-UrlResponding([string]$Url, [int]$TimeoutSec = 2) {
    try {
        $resp = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSec -UseBasicParsing -ErrorAction SilentlyContinue
        return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400)
    } catch {
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
            return ($code -ge 200 -and $code -lt 400)
        }
        return $false
    }
}

function Stop-PortProcess([int]$Port) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            if ($c.OwningProcess -and $c.OwningProcess -gt 0) {
                Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {}
}

function Stop-ProcessFile([string]$ServiceName) {
    $pidFile = Join-Path $PidDir "$ServiceName.pid"
    if (Test-Path $pidFile) {
        $p = Get-Content $pidFile -ErrorAction SilentlyContinue | Out-String
        $p = $p.Trim()
        if ($p -match '^\d+$') {
            Write-Host "  Stopping $ServiceName (PID $p)... " -NoNewline
            try {
                Stop-Process -Id ([int]$p) -Force -ErrorAction SilentlyContinue
                Write-Host "done" -ForegroundColor Green
            } catch {
                Write-Host "already stopped" -ForegroundColor Gray
            }
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}

function Stop-AllServices {
    Write-Step "Stopping all local services"
    Stop-ProcessFile "frontend"
    Stop-ProcessFile "backend"
    Stop-ProcessFile "worker"
    Stop-ProcessFile "opencode"

    # Stop Docker if compose exists
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        try {
            docker compose stop | Out-Null
            Write-Host "  Docker containers stopped." -ForegroundColor Green
        } catch {}
    }
    Write-Success "All services stopped."
}

function Show-ServiceStatus {
    Write-Step "AI Solution Builder Service Status"

    function Check-ServiceStatus([string]$Name, [int]$Port, [string]$Url) {
        $pidFile = Join-Path $PidDir "$Name.pid"
        $pidVal = "-"
        if (Test-Path $pidFile) {
            $pidVal = (Get-Content $pidFile -ErrorAction SilentlyContinue | Out-String).Trim()
        }

        $status = "STOPPED"
        $color = "Red"

        if ($Name -eq "worker") {
            if ($pidVal -match '^\d+$' -and (Get-Process -Id ([int]$pidVal) -ErrorAction SilentlyContinue)) {
                $status = "RUNNING (PID $pidVal)"
                $color = "Green"
            } else {
                $status = "STOPPED / INLINE"
                $color = "Yellow"
            }
        } elseif ($Port -gt 0 -and (Test-PortListening $Port)) {
            if ($Url -and (Test-UrlResponding $Url)) {
                $status = "HEALTHY (HTTP 200)"
                $color = "Green"
            } else {
                $status = "LISTENING (port $Port)"
                $color = "Yellow"
            }
        }

        Write-Host ("  {0,-14} Port: {1,-6} PID: {2,-8} Status: " -f $Name, $Port, $pidVal) -NoNewline
        Write-Host $status -ForegroundColor $color
    }

    Check-ServiceStatus "backend"  8000 "$BackendUrl/health"
    Check-ServiceStatus "frontend" 3000 "$FrontendUrl"
    Check-ServiceStatus "opencode" 4096 "$SidecarUrl"
    Check-ServiceStatus "worker"   0    ""

    if (Get-Command docker -ErrorAction SilentlyContinue) {
        Write-Host "`n  Docker containers:" -ForegroundColor Cyan
        docker compose ps 2>$null
    }
}

function Wait-ForService([string]$Name, [string]$Url, [int]$TimeoutSec, [string]$LogFile = "") {
    Write-Host ("  Waiting for {0,-26}" -f $Name) -NoNewline
    $elapsed = 0
    while ($elapsed -lt $TimeoutSec) {
        if (Test-UrlResponding $Url) {
            Write-Host " OK ($Url)" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 2
        $elapsed += 2
    }
    Write-Host " TIMEOUT ($Url)" -ForegroundColor Red
    if ($LogFile -and (Test-Path $LogFile)) {
        Write-Host "`n--- Last 15 lines of $LogFile ---" -ForegroundColor Yellow
        Get-Content $LogFile -Tail 15 -ErrorAction SilentlyContinue
        Write-Host "---------------------------------`n" -ForegroundColor Yellow
    }
    return $false
}

function Prune-Docker {
    Write-Step "Reclaiming C: drive space from Docker Desktop"
    docker system df
    Write-Step "1. Stopping and removing old containers..."
    docker compose stop 2>$null
    docker compose rm -f 2>$null
    docker container prune -f 2>$null
    Write-Step "2. Pruning dangling Docker build cache..."
    docker builder prune -f
    Write-Step "3. Pruning dangling images..."
    docker image prune -f
    Write-Step "4. Removing large custom images..."
    docker rmi ai_solution_builder-backend ai_solution_builder-worker ai_solution_builder-opencode ai_solution_builder-frontend 2>$null
    Write-Step "Docker disk usage after cleanup:"
    docker system df
    Write-Success "Docker cleanup complete. Your C: drive has reclaimed space."
}

function Start-NativeStack([bool]$Detached = $false) {
    Write-Step "Checking prerequisites for Native Mode (No Docker)"

    # Find Python
    $pythonBin = ""
    $candidates = @(
        (Join-Path $ScriptDir "backend\.venv\Scripts\python.exe"),
        (Join-Path $ScriptDir ".venv\Scripts\python.exe")
    )
    foreach ($cand in $candidates) {
        if (Test-Path $cand) {
            $pythonBin = $cand
            break
        }
    }
    if (-not $pythonBin) {
        if (Get-Command python -ErrorAction SilentlyContinue) {
            $pythonBin = (Get-Command python).Source
        } else {
            Write-Err "Python not found. Please install Python 3.12+ or create backend\.venv."
            exit 1
        }
    }

    Write-Success "Python:   $(& $pythonBin --version) ($pythonBin)"
    Write-Success "Node.js:  $(node --version) ($(Get-Command node).Source)"
    Write-Success "npm:      $(npm --version)"

    $opencodeBin = Get-Command opencode -ErrorAction SilentlyContinue
    if ($opencodeBin) {
        Write-Success "OpenCode: installed ($($opencodeBin.Source))"
    } else {
        Write-Warn "opencode CLI not found. Install via: npm i -g opencode"
    }

    if (-not (Test-Path (Join-Path $ScriptDir "frontend\node_modules"))) {
        Write-Step "Installing frontend dependencies (npm install)..."
        Push-Location (Join-Path $ScriptDir "frontend")
        npm install
        Pop-Location
    }

    # Free ports if leftover
    Stop-PortProcess 8000
    Stop-PortProcess 3000

    # 1. OpenCode Sidecar
    Write-Step "Starting OpenCode sidecar on port 4096"
    if (Test-PortListening 4096 -or (Test-UrlResponding "$SidecarUrl/global/health")) {
        Write-Success "OpenCode sidecar already listening on port 4096 - reusing."
    } elseif ($opencodeBin) {
        $ocDir = Join-Path $ScriptDir "backend\opencode"
        $ocLog = Join-Path $LogDir "opencode.log"
        $p = Start-Process -FilePath "opencode" -ArgumentList "serve --port 4096 --hostname 127.0.0.1" `
            -WorkingDirectory $ocDir -RedirectStandardOutput $ocLog -RedirectStandardError $ocLog `
            -PassThru -WindowStyle Hidden
        Set-Content -Path (Join-Path $PidDir "opencode.pid") -Value $p.Id
        Write-Success "OpenCode started (PID $($p.Id))"
    }

    # 2. FastAPI Backend
    Write-Step "Starting FastAPI Backend API on port 8000"
    $bkDir = Join-Path $ScriptDir "backend"
    $bkLog = Join-Path $LogDir "backend.log"
    $env:MVP_BUILD_DIR = (Join-Path $DataDir "mvp_builds")
    $p = Start-Process -FilePath $pythonBin -ArgumentList "-m uvicorn main:app --host 127.0.0.1 --port 8000" `
        -WorkingDirectory $bkDir -RedirectStandardOutput $bkLog -RedirectStandardError $bkLog `
        -PassThru -WindowStyle Hidden
    Set-Content -Path (Join-Path $PidDir "backend.pid") -Value $p.Id
    Write-Success "Backend started (PID $($p.Id))"

    # 3. Worker
    $workerMode = "inline"
    if (Test-Path ".env") {
        $m = Select-String -Path ".env" -Pattern '^WORKER_MODE=(.*)' | Select-Object -First 1
        if ($m -and $m.Matches[0].Groups[1].Value.Trim() -eq "worker") {
            $workerMode = "worker"
        }
    }
    if ($workerMode -eq "worker") {
        Write-Step "Starting Build Worker process (WORKER_MODE=worker)"
        $wkLog = Join-Path $LogDir "worker.log"
        $p = Start-Process -FilePath $pythonBin -ArgumentList "-m app.worker" `
            -WorkingDirectory $bkDir -RedirectStandardOutput $wkLog -RedirectStandardError $wkLog `
            -PassThru -WindowStyle Hidden
        Set-Content -Path (Join-Path $PidDir "worker.pid") -Value $p.Id
        Write-Success "Worker started (PID $($p.Id))"
    } else {
        Write-Success "Worker mode: inline"
    }

    # 4. Frontend Next.js
    Write-Step "Starting Next.js Frontend on port 3000"
    $feDir = Join-Path $ScriptDir "frontend"
    $feLog = Join-Path $LogDir "frontend.log"
    $p = Start-Process -FilePath "npm.cmd" -ArgumentList "run dev -- --port 3000" `
        -WorkingDirectory $feDir -RedirectStandardOutput $feLog -RedirectStandardError $feLog `
        -PassThru -WindowStyle Hidden
    Set-Content -Path (Join-Path $PidDir "frontend.pid") -Value $p.Id
    Write-Success "Frontend started (PID $($p.Id))"

    # 5. Wait for health
    Write-Step "Waiting for services to become healthy..."
    $failed = $false
    if (-not (Wait-ForService "Backend /health" "$BackendUrl/health" $HealthTimeout (Join-Path $LogDir "backend.log"))) { $failed = $true }
    if (-not (Wait-ForService "Backend /ready"  "$BackendUrl/ready"  $HealthTimeout (Join-Path $LogDir "backend.log"))) { $failed = $true }
    if (-not (Wait-ForService "Frontend"        $FrontendUrl        $HealthTimeout (Join-Path $LogDir "frontend.log"))) { $failed = $true }
    if ($opencodeBin) {
        Wait-ForService "OpenCode Sidecar" $SidecarUrl 30 (Join-Path $LogDir "opencode.log") | Out-Null
    }

    if ($failed) {
        Write-Warn "One or more services did not become ready within timeout."
        Write-Warn "Inspect logs in: .data\logs\"
    } else {
        Write-Host "`nAll services are up and healthy!" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "  AI Solution Builder is running locally (Zero Docker / Native Mode)" -ForegroundColor White
    Write-Host ""
    Write-Host ("  -> Frontend:        {0}" -f $FrontendUrl) -ForegroundColor Cyan
    Write-Host ("  -> Backend API:     {0}" -f $BackendUrl) -ForegroundColor Cyan
    Write-Host ("  -> API Docs:        {0}/docs" -f $BackendUrl) -ForegroundColor Cyan
    Write-Host ("  -> Health Probes:   {0}/health  |  {0}/ready" -f $BackendUrl)
    Write-Host ("  -> OpenCode:        {0}" -f $SidecarUrl) -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Commands:" -ForegroundColor Yellow
    Write-Host "    .\run_local.ps1 -Status    Check status of all services"
    Write-Host "    .\run_local.ps1 -Stop      Stop all services"
    Write-Host "    .\run_local.ps1 -Prune     Clean Docker build cache and reclaim C: drive"
    Write-Host ""

    if ($Detached) {
        Write-Success "Running detached in background."
    } else {
        Write-Host "Press Ctrl+C at any time to shut down the stack." -ForegroundColor Gray
        try {
            while ($true) { Start-Sleep -Seconds 2 }
        } finally {
            Stop-AllServices
        }
    }
}

# -- Router ------------------------------------------
if ($Stop) {
    Stop-AllServices
    exit 0
}
if ($Status) {
    Show-ServiceStatus
    exit 0
}
if ($Prune) {
    Prune-Docker
    exit 0
}
if ($Down) {
    Stop-AllServices
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        docker compose down -v 2>$null
    }
    exit 0
}
if ($Infra) {
    docker compose up -d postgres redis
    Start-NativeStack $false
    exit 0
}
if ($Docker -or $DockerBuild) {
    if ($DockerBuild) {
        docker compose up --build -d
    } else {
        docker compose up -d
    }
    exit 0
}

switch ($Command.ToLower()) {
    "stop"    { Stop-AllServices }
    "status"  { Show-ServiceStatus }
    "prune"   { Prune-Docker }
    "down"    { Stop-AllServices; docker compose down -v 2>$null }
    "infra"   { docker compose up -d postgres redis; Start-NativeStack $false }
    "docker"  { docker compose up -d }
    default   { Start-NativeStack $Detach }
}
