@echo off
chcp 65001 >nul

:: Port 8000 ve 5174'te kalan eski process'leri temizle
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5174 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
)

powershell.exe -ExecutionPolicy Bypass -File "%~dp0start.ps1"
