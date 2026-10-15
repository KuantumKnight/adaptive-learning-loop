[CmdletBinding()]
param(
    [string]$ProjectName = "idp-acceptance"
)

$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent $PSScriptRoot
$resultPath = Join-Path $workspace "artifacts/postgres-verification.json"
$compose = @(
    "-p", $ProjectName,
    "-f", (Join-Path $workspace "docker-compose.yml"),
    "-f", (Join-Path $workspace "docker-compose.acceptance.yml")
)

function Write-Result([hashtable]$result) {
    New-Item -ItemType Directory -Force (Split-Path -Parent $resultPath) | Out-Null
    $result.checked_at = (Get-Date).ToUniversalTime().ToString("o")
    $result | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 $resultPath
}

try {
    docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Docker Desktop Linux engine is unavailable" }
} catch {
    Write-Result @{ status = "blocked_external"; reason = "Docker Desktop Linux engine is unavailable"; evidence = $_.Exception.Message }
    Write-Output "Docker is unavailable. See $resultPath"
    exit 2
}

$started = $false
try {
    & docker compose @compose up -d --build db backend
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed with exit code $LASTEXITCODE" }
    $started = $true

    $healthCode = 'import urllib.request; urllib.request.urlopen("http://localhost:8000/health/ready", timeout=5).read()'
    & docker compose @compose exec -T backend python -c $healthCode | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "backend readiness check failed" }

    $tableCode = 'import urllib.request; print(urllib.request.urlopen("http://localhost:8000/health/ready").read().decode())'
    $health = (& docker compose @compose exec -T backend python -c $tableCode | Out-String).Trim()
    if ($health -notmatch 'ready') { throw "unexpected readiness response: $health" }

    $createCode = 'import json,urllib.request; body=json.dumps({"participant_code":"postgres-acceptance","mode":"static","lesson_id":"binary-search","study_kind":"practice"}).encode(); req=urllib.request.Request("http://localhost:8000/api/sessions", data=body, headers={"Content-Type":"application/json"}); print(json.dumps(json.load(urllib.request.urlopen(req))))'
    $created = ((& docker compose @compose exec -T backend python -c $createCode) | Out-String).Trim() | ConvertFrom-Json
    if (-not $created.session_id -or -not $created.access_token) { throw "session creation did not return a token" }

    & docker compose @compose restart db | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "database restart failed" }
    Start-Sleep -Seconds 5
    & docker compose @compose restart backend | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "backend restart failed" }
    Start-Sleep -Seconds 3
    & docker compose @compose exec -T backend python -c $healthCode | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "backend readiness failed after restart" }

    $resumeCode = 'import json,urllib.request,sys; sid=sys.argv[1]; token=sys.argv[2]; req=urllib.request.Request("http://localhost:8000/api/sessions/"+sid, headers={"X-Session-Token":token}); print(json.dumps(json.load(urllib.request.urlopen(req))))'
    $resumed = ((& docker compose @compose exec -T backend python -c $resumeCode $created.session_id $created.access_token) | Out-String).Trim() | ConvertFrom-Json
    if ($resumed.id -ne $created.session_id) { throw "session did not survive database/backend restart" }

    Write-Result @{ status = "verified"; project = $ProjectName; session_id = $created.session_id; health = $health; persistence = "session survived database and backend restart" }
    Write-Output "PostgreSQL acceptance verification passed. See $resultPath"
} catch {
    Write-Result @{ status = "failed"; project = $ProjectName; reason = $_.Exception.Message }
    Write-Error "PostgreSQL acceptance verification failed. See $resultPath"
    exit 1
} finally {
    if ($started) {
        & docker compose @compose down -v | Out-Null
    }
}
