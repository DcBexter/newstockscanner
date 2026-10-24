@echo off
pushd backend
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
python -m pytest --disable-socket --allow-unix-socket --cov --cov-branch --cov-report=xml
set TEST_EXIT=%ERRORLEVEL%
popd
exit /b %TEST_EXIT%
