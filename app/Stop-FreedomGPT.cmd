@echo off
cd /d "%~dp0"
"%~dp0runtime\python\python.exe" -s "%~dp0stop.py"
pause
