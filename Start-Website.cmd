@echo off
cd /d "%~dp0"
set TEMP=%~dp0.tmp
set TMP=%~dp0.tmp
set PYTHONDONTWRITEBYTECODE=1
start "Freedom GPT website" "%~dp0build\FreedomGPT\runtime\python\pythonw.exe" -s "%~dp0site\launch.py"
