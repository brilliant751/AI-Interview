@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0test-windows.ps1" %*
exit /b %ERRORLEVEL%
