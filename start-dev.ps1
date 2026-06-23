# Opens backend + frontend in two separate PowerShell windows (bypasses Cursor terminal limits).
# Usage:  .\start-dev.ps1

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ApiPort = if ($env:API_PORT) { $env:API_PORT } else { "8001" }
$HealthUrl = "http://127.0.0.1:$ApiPort/api/health"

function Wait-ForBackend {
    param([int]$TimeoutSeconds = 60)
    Write-Host "Waiting for backend at $HealthUrl ..."
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) {
                Write-Host "Backend is ready."
                return $true
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    Write-Host "ERROR: Backend did not start within ${TimeoutSeconds}s." -ForegroundColor Red
    Write-Host "Check the BACKEND window for errors (port $ApiPort in use? missing venv?)."
    return $false
}

Write-Host "Starting Dutch Road Accident Map..."
Write-Host "  Backend:  http://127.0.0.1:$ApiPort"
Write-Host "  Frontend: http://localhost:5173"
Write-Host ""

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Root'; Write-Host '=== BACKEND (API) ===' -ForegroundColor Cyan; .\make.ps1 backend"
)

if (-not (Wait-ForBackend)) {
    exit 1
}

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Root'; Write-Host '=== FRONTEND (MAP) ===' -ForegroundColor Green; .\make.ps1 frontend"
)

Write-Host ""
Write-Host "Frontend window opened. Open http://localhost:5173 in your browser."
