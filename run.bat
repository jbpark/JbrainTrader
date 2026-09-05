@echo off
setlocal
chcp 65001 >nul

:: Control logic is handled by run.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
