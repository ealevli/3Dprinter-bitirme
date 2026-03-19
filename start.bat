@echo off
setlocal enabledelayedexpansion
title 3D Yazici Kaplama Sistemi

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "VENV=%ROOT%\.venv"

echo.
echo  ==========================================
echo   3D Yazici Kaplama Sistemi -- Baslatici
echo  ==========================================
echo.

:: ── 1. Python check ───────────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python bulunamadi. Luetfen Python 3.10+ yukleyin: https://python.org
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [INFO]  %PY_VER% bulundu.

:: ── 2. Virtual environment ────────────────────────────────────────────────────
if not exist "%VENV%\Scripts\activate.bat" (
    echo [INFO]  Sanal ortam olusturuluyor (.venv)...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERROR] Sanal ortam olusturulamadi.
        pause
        exit /b 1
    )
    echo [OK]    Sanal ortam olusturuldu.
)

call "%VENV%\Scripts\activate.bat"

:: ── 3. Python dependencies ────────────────────────────────────────────────────
echo [INFO]  Python bagimliliklar kontrol ediliyor...
python -m pip install -q --upgrade pip
python -m pip install -q -r "%ROOT%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Bagimlilik yuklemesi basarisiz. Internet baglantinizi kontrol edin.
    pause
    exit /b 1
)
echo [OK]    Python bagimliliklar hazir.

:: ── 4. Node / npm check ───────────────────────────────────────────────────────
where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm bulunamadi. Luetfen Node.js 18+ yukleyin: https://nodejs.org
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do set NODE_VER=%%v
echo [INFO]  Node %NODE_VER% bulundu.

:: ── 5. Frontend dependencies ──────────────────────────────────────────────────
if not exist "%FRONTEND%\node_modules" (
    echo [INFO]  npm install calistiriliyor...
    pushd "%FRONTEND%"
    npm install --silent
    if errorlevel 1 (
        echo [ERROR] npm install basarisiz.
        pause
        exit /b 1
    )
    popd
    echo [OK]    Frontend bagimliliklar hazir.
) else (
    echo [INFO]  node_modules mevcut, atlaniyor.
)

:: ── 6. Launch backend ─────────────────────────────────────────────────────────
echo [INFO]  Backend baslatiliyor (http://localhost:8000)...
pushd "%BACKEND%"
start "Coating-Backend" /min cmd /c "call "%VENV%\Scripts\activate.bat" && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
popd

:: Give the backend a moment to start
timeout /t 2 /nobreak >nul

:: ── 7. Launch frontend ────────────────────────────────────────────────────────
echo [INFO]  Frontend baslatiliyor (http://localhost:5173)...
pushd "%FRONTEND%"
start "Coating-Frontend" /min cmd /c "npm run dev"
popd

timeout /t 3 /nobreak >nul

echo.
echo [OK]    Sistem calisiyor!
echo.
echo   Backend  --^> http://localhost:8000
echo   Frontend --^> http://localhost:5173
echo   API Docs --^> http://localhost:8000/docs
echo.
echo Tarayici aciliyor...
start "" "http://localhost:5173"

echo.
echo Sistemi durdurmak icin bu pencereyi kapatin veya
echo Gorev Yoneticisi'nden "Coating-Backend" ve "Coating-Frontend"
echo pencerelerini kapatin.
echo.
pause
