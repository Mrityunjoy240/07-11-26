Write-Host "Starting BCREC AI infrastructure..." -ForegroundColor Green

# Check Docker
$dockerRunning = $false
try {
    $null = docker ps 2>&1
    $dockerRunning = $true
} catch {
    Write-Host "Docker is not running. Attempting to start Docker Desktop..." -ForegroundColor Yellow
    try {
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        Write-Host "Waiting for Docker to start..." -ForegroundColor Yellow
        Start-Sleep -Seconds 20
        $null = docker ps 2>&1
        $dockerRunning = $true
    } catch {
        Write-Host "Failed to start Docker. Please start Docker Desktop manually." -ForegroundColor Red
        exit 1
    }
}

if ($dockerRunning) {
    Write-Host "Starting Redis + PostgreSQL..." -ForegroundColor Green
    docker compose -f docker-compose.yml up -d

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Waiting for services to be healthy..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
        docker compose ps
        Write-Host "Infrastructure is ready!" -ForegroundColor Green
    } else {
        Write-Host "Failed to start services." -ForegroundColor Red
    }
}
