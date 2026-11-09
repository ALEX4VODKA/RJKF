@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
set "PYTHON=%PROJECT_ROOT%.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo Missing project virtual environment: %PYTHON%
  echo Please install dependencies according to README.md first.
  pause
  exit /b 1
)
"%PYTHON%" "%PROJECT_ROOT%Module A\parking_system\tools\start_defense_demo.py"
if errorlevel 1 pause
endlocal
