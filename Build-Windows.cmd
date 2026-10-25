@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0source\launchers\Build-Atlas.ps1" -Target windows19 %*
exit /b %errorlevel%
