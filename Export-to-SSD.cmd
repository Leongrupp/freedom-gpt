@echo off
cd /d "%~dp0"
set TEMP=%~dp0.tmp
set TMP=%~dp0.tmp
set PYTHONDONTWRITEBYTECODE=1
"%~dp0build\FreedomGPT\runtime\python\python.exe" "%~dp0packaging\export_ssd.py" --include-models --include-history
pause
