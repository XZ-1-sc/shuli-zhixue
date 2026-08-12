$ErrorActionPreference = "Stop"

$env:DOCKER_BUILDKIT = "0"

docker build -f docker/backend/Dockerfile -t math-smartbrain-backend:local .
docker build -f docker/gateway/Dockerfile -t math-smartbrain-gateway:local .

Write-Host "Docker images built with legacy builder:"
Write-Host "  math-smartbrain-backend:local"
Write-Host "  math-smartbrain-gateway:local"
Write-Host ""
Write-Host "Next command:"
Write-Host "  docker compose up -d"
