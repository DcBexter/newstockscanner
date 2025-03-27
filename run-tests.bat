@echo off
pushd backend
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
python -m pytest --cov --cov-branch --cov-report=xml
popd
