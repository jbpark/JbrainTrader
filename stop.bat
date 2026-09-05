@echo off
setlocal
chcp 65001 >nul

:: Stop logic is handled by stop.ps1 to avoid CMD escaping issues
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"
