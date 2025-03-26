@echo off
echo Starting application in DEV mode with hot reload
echo NODE_ENV=dev is set automatically in docker-compose.dev.yml
echo Frontend will be available at: http://localhost:5173
echo API will be available at: http://localhost:8000

set "COMPOSE_BAKE=false" && docker-compose -f docker-compose.dev.yml up --build