@echo off
chcp 65001 >nul
title Vue Frontend

:: Vite 캐시 삭제 (Pre-transform error 방지)
if exist "node_modules\.vite" (
    rd /s /q "node_modules\.vite"
    echo [*] Vite 캐시 초기화 완료
)

node start_with_title.js
