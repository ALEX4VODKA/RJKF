@echo off
setlocal
cd /d "%~dp0"
"%~dp0智慧停车收费系统.exe" --defense-mode
if errorlevel 1 pause
endlocal
