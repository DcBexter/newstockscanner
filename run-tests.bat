@echo off
echo Running tests in Docker container
echo Tests will be run against a PostgreSQL database in a Docker container
echo Test database: backend_test

set "COMPOSE_BAKE=false" && docker compose -f docker-compose.test.yml up --build
if %errorlevel% neq 0 (
    echo Docker Compose build failed with error code %errorlevel%
    exit /b %errorlevel%
)