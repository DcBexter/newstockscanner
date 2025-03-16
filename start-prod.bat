@echo off
echo Starting application in PROD mode
echo NODE_ENV=prod is used from .env file
echo Frontend will be available at: http://localhost:80
echo API will be available at: http://localhost:8000

docker-compose up --build 