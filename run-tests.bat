@echo off
cd backend
python -m pytest --cov --cov-branch --cov-report=xml
cd ..
