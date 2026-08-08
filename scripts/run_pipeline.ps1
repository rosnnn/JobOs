# One-command pipeline runner for Job OS (Windows PowerShell)
# Usage: .\scripts\run_pipeline.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path .env)) { Copy-Item .env.example .env }

Write-Host "==> Starting Docker (Postgres:5433, Redis:6380)..."
docker compose up -d postgres redis | Out-Null
Start-Sleep -Seconds 8

$env:PYTHONPATH = "src"
Remove-Item Env:JOB_OS_DATABASE_URL -ErrorAction SilentlyContinue

Write-Host "==> Ingesting resume..."
.\.venv\Scripts\python scripts\ingest_resume.py --no-sync-world

Write-Host "==> Initializing database..."
.\.venv\Scripts\python scripts/init_db.py

Write-Host "==> Starting API on http://127.0.0.1:8000 ..."
$uvicorn = ".\.venv\Scripts\uvicorn.exe"
$existing = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if (-not $existing) {
    Start-Process -WindowStyle Hidden -FilePath $uvicorn -ArgumentList "job_os.main:app","--host","127.0.0.1","--port","8000"
    Start-Sleep -Seconds 5
}

Write-Host "==> Running daily_discovery workflow (may take 1-2 min)..."
$wf = Invoke-RestMethod -Uri "http://127.0.0.1:8000/workflows" -Method POST -Body '{"workflow_type":"daily_discovery"}' -ContentType "application/json" -TimeoutSec 600
Write-Host "Workflow $($wf.id) status: $($wf.status)"

$apps = Invoke-RestMethod -Uri "http://127.0.0.1:8000/applications?limit=10"
Write-Host "Draft applications: $($apps.Count)"
$apps | Select-Object id, job_title, company_name, approval_status | Format-Table -AutoSize

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Review:  GET http://127.0.0.1:8000/applications"
Write-Host "  2. Approve: POST http://127.0.0.1:8000/applications/{id}/approve"
Write-Host "  3. Dry-run apply: POST http://127.0.0.1:8000/applications/{id}/submit  body: {\"dry_run\":true}"
Write-Host "  4. OpenAPI docs: http://127.0.0.1:8000/docs"
