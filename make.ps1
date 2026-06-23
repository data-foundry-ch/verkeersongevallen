# Windows-friendly task runner (PowerShell).
# Usage:  .\make.ps1 profile
#         .\make.ps1 pipeline
#         .\make.ps1 backend

param(
    [Parameter(Position = 0)]
    [string]$Target = "help"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }
$ApiPort = if ($env:API_PORT) { $env:API_PORT } else { "8001" }

function Get-PortListenerPids {
    param([string]$Port)
    $pids = @()
    try {
        $pids += Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    } catch { }
    $netstat = netstat -ano | Select-String ":$Port\s+.*LISTENING"
    foreach ($line in $netstat) {
        if ($line -match '\s+(\d+)\s*$') {
            $pids += [int]$Matches[1]
        }
    }
    $pids = @($pids | Where-Object { $_ -and $_ -gt 0 } | Select-Object -Unique)

    try {
        $python = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
        foreach ($proc in $python) {
            $cmd = $proc.CommandLine
            if (-not $cmd) { continue }
            if ($cmd -match 'uvicorn' -and ($cmd -match "port\s+$Port" -or $cmd -match "--port\s+$Port" -or $cmd -match 'backend\.app\.main')) {
                $pids += $proc.ProcessId
            }
            foreach ($parentPid in $pids) {
                if ($cmd -match "parent_pid=$parentPid") {
                    $pids += $proc.ProcessId
                }
            }
        }
    } catch { }

    $pids | Where-Object { $_ -and $_ -gt 0 } | Select-Object -Unique
}

function Stop-ApiPort {
    param([string]$Port)
    $deadline = (Get-Date).AddSeconds(20)
    do {
        $pids = Get-PortListenerPids -Port $Port
        foreach ($procId in $pids) {
            Write-Host "Stopping PID $procId (port $Port)..."
            & taskkill.exe /PID $procId /F /T 2>$null | Out-Null
        }
        Start-Sleep -Seconds 1
        $still = Get-PortListenerPids -Port $Port
    } while ($still.Count -gt 0 -and (Get-Date) -lt $deadline)

    if ((Get-PortListenerPids -Port $Port).Count -gt 0) {
        Write-Host "ERROR: Port $Port is still in use after stop attempts." -ForegroundColor Red
        Write-Host "Run in an elevated terminal: netstat -ano | findstr :$Port"
        Write-Host "Then: taskkill /PID <pid> /F /T"
        exit 1
    }
}

function Run-Pipeline {
    & $Python scripts/00_profile_raw_data.py
    & $Python scripts/01_ingest_to_duckdb.py
    & $Python scripts/02_build_normalized_tables.py
    & $Python scripts/03_build_a2_bins.py
    & $Python scripts/04_validate_a2_outputs.py
    Write-Host "Full A2 pipeline complete."
}

switch ($Target.ToLower()) {
    "profile"   { & $Python scripts/00_profile_raw_data.py }
    "ingest"    { & $Python scripts/01_ingest_to_duckdb.py }
    "normalize" { & $Python scripts/02_build_normalized_tables.py }
    "bins"      { & $Python scripts/03_build_a2_bins.py }
    "validate"  { & $Python scripts/04_validate_a2_outputs.py }
    "split-raw" { & $Python scripts/05_split_databases.py raw }
    "export-deploy" { & $Python scripts/05_split_databases.py deploy }
    "split-db"  { & $Python scripts/05_split_databases.py all }
    "pipeline"  { Run-Pipeline }
    "backend"   {
        if ((Get-PortListenerPids -Port $ApiPort).Count -gt 0) {
            $procId = (Get-PortListenerPids -Port $ApiPort | Select-Object -First 1)
            Write-Host "ERROR: Port $ApiPort is already in use (PID $procId)." -ForegroundColor Red
            Write-Host "Run: .\make.ps1 restart-backend"
            exit 1
        }

        Write-Host "Starting API on http://127.0.0.1:$ApiPort (docs: /docs, health: /api/health)"
        $uvicorn = if (Test-Path (Join-Path $Root ".venv\Scripts\uvicorn.exe")) {
            Join-Path $Root ".venv\Scripts\uvicorn.exe"
        } else {
            "uvicorn"
        }

        $uvicornArgs = @("backend.app.main:app", "--host", "127.0.0.1", "--port", $ApiPort)
        if ($env:DEV_RELOAD -eq "1") {
            Write-Host "DEV_RELOAD=1 - hot reload enabled (backend/app only)"
            $uvicornArgs += @("--reload", "--reload-dir", "backend/app")
        } else {
            Write-Host "Stable mode (no hot reload). Set `$env:DEV_RELOAD=1 to enable reload."
        }
        & $uvicorn @uvicornArgs
    }
    "restart-backend" {
        Stop-ApiPort -Port $ApiPort
        & $MyInvocation.MyCommand.Path backend
    }
    "stop-backend" {
        Stop-ApiPort -Port $ApiPort
        Write-Host "Backend on port $ApiPort stopped."
    }
    "frontend"  {
        Push-Location frontend
        npm run dev
        Pop-Location
    }
    "install"   {
        & $Python -m pip install -e ".[dev]"
        Push-Location frontend
        npm install
        Pop-Location
    }
    "dev" {
        Write-Host "Option A - one command, two windows:"
        Write-Host "  .\start-dev.ps1"
        Write-Host ""
        Write-Host "Option B - manually in two Cursor terminals (Terminal > New Terminal):"
        Write-Host "  .\make.ps1 backend"
        Write-Host "  .\make.ps1 frontend"
    }
    "help" {
        Write-Host @"
Dutch Road Accident Map - tasks (Windows)

  .\make.ps1 install     Install Python + npm dependencies
  .\make.ps1 profile     Profile raw data
  .\make.ps1 ingest      Ingest into DuckDB
  .\make.ps1 normalize   Build normalized tables
  .\make.ps1 bins        Build A2 bins
  .\make.ps1 validate    Validation report
  .\make.ps1 split-raw   Step 1: export raw_* tables to accidents_raw.duckdb
  .\make.ps1 export-deploy  Step 2: slim API DB to accidents_deploy.duckdb
  .\make.ps1 split-db    Both split steps
  .\make.ps1 pipeline    Run profile -> validate
  .\make.ps1 backend          FastAPI on http://localhost:8001
  .\make.ps1 restart-backend  Stop + start backend (fixes stuck port)
  .\make.ps1 stop-backend     Stop backend on port 8001
  .\make.ps1 frontend    Vite on http://localhost:5173
  .\make.ps1 dev         Show dev-server instructions

Git Bash: use ./tasks.sh instead of make
CMD:      tasks.cmd profile
"@
    }
    default {
        Write-Error "Unknown target '$Target'. Run: .\make.ps1 help"
    }
}
