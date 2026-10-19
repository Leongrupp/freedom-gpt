@echo off
cd /d "%~dp0"
start "Freedom GPT" "%~dp0runtime\python\pythonw.exe" -s "%~dp0launch.py"
