$ROOT     = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND  = "$ROOT\backend"
$FRONTEND = "$ROOT\frontend"
$VENV     = "$ROOT\.venv"          # macOS ile aynı yol — tutarlılık

Write-Host ""
Write-Host " ==========================================" -ForegroundColor Cyan
Write-Host "   3D Yazici Kaplama Sistemi -- Baslatici"  -ForegroundColor Cyan
Write-Host " ==========================================" -ForegroundColor Cyan
Write-Host ""

# ── 0. Port temizligi ─────────────────────────────────────────────────────────
foreach ($port in @(8000, 5174)) {
    $pids = (netstat -ano | Select-String ":$port " | Select-String "LISTENING") |
            ForEach-Object { ($_ -split '\s+')[-1] } | Select-Object -Unique
    foreach ($p in $pids) {
        if ($p -match '^\d+$') {
            Write-Host "[WARN]  Port $port mesgul, temizleniyor (PID $p)..." -ForegroundColor Yellow
            taskkill /PID $p /F 2>$null | Out-Null
        }
    }
}

# ── 1. Python check ───────────────────────────────────────────────────────────
$pyCmd = $null
foreach ($candidate in @("python", "python3", "py")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $pyCmd = $candidate; break
    }
}
if (-not $pyCmd) {
    Write-Host "[ERROR] Python bulunamadi. Lutfen Python 3.10+ yukleyin." -ForegroundColor Red
    Read-Host "Cikis icin Enter'a basin"
    exit 1
}
$pyVer = & $pyCmd --version 2>&1
Write-Host "[INFO]  $pyVer bulundu." -ForegroundColor Cyan

# ── 2. Venv ───────────────────────────────────────────────────────────────────
if (-not (Test-Path "$VENV\Scripts\activate.ps1")) {
    Write-Host "[INFO]  Sanal ortam olusturuluyor (.venv)..." -ForegroundColor Yellow
    & $pyCmd -m venv "$VENV"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Sanal ortam olusturulamadi." -ForegroundColor Red
        Read-Host "Cikis icin Enter'a basin"
        exit 1
    }
    Write-Host "[OK]    Sanal ortam olusturuldu." -ForegroundColor Green
}

& "$VENV\Scripts\activate.ps1"

# ── 3. Python bagimliliklar ───────────────────────────────────────────────────
Write-Host "[INFO]  Python bagimliliklar yukleniyor..." -ForegroundColor Cyan
pip install -q -r "$ROOT\requirements.txt"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Bagimlilik yuklemesi basarisiz. requirements.txt kontrol edin." -ForegroundColor Red
    Read-Host "Cikis icin Enter'a basin"
    exit 1
}
Write-Host "[OK]    Python bagimliliklar hazir." -ForegroundColor Green

# ── 4. Node check ─────────────────────────────────────────────────────────────
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] npm bulunamadi. Lutfen Node.js 18+ yukleyin." -ForegroundColor Red
    Read-Host "Cikis icin Enter'a basin"
    exit 1
}
$nodeVer = node --version
Write-Host "[INFO]  Node $nodeVer bulundu." -ForegroundColor Cyan

# ── 5. Frontend bagimliliklar ─────────────────────────────────────────────────
$needsInstall = $false
if (-not (Test-Path "$FRONTEND\node_modules")) {
    $needsInstall = $true
} else {
    # rollup native binding platform uyumluluk kontrolu
    $rollupTest = node -e "require('$FRONTEND\node_modules\rollup\dist\native.js')" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN]  node_modules farkli platformda kurulmus, yeniden yukleniyor..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force "$FRONTEND\node_modules" -ErrorAction SilentlyContinue
        Remove-Item -Force "$FRONTEND\package-lock.json" -ErrorAction SilentlyContinue
        $needsInstall = $true
    }
}

if ($needsInstall) {
    Write-Host "[INFO]  npm install calistiriliyor..." -ForegroundColor Yellow
    Set-Location $FRONTEND
    npm install --silent
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Frontend bagimliliklar yuklenemedi." -ForegroundColor Red
        Set-Location $ROOT
        Read-Host "Cikis icin Enter'a basin"
        exit 1
    }
    Set-Location $ROOT
    Write-Host "[OK]    Frontend bagimliliklar hazir." -ForegroundColor Green
} else {
    Write-Host "[INFO]  node_modules hazir." -ForegroundColor Cyan
}

# ── 6. Backend baslat ─────────────────────────────────────────────────────────
Write-Host "[INFO]  Backend baslatiliyor (http://localhost:8000)..." -ForegroundColor Cyan
$backendLog = "$ROOT\.backend.log"
Start-Process powershell -ArgumentList `
    "-NoExit", "-Command",
    "& '$VENV\Scripts\activate.ps1'; Set-Location '$BACKEND'; python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload 2>&1 | Tee-Object -FilePath '$backendLog'" `
    -WindowStyle Minimized

# Backend hazir olana kadar bekle (max 15s)
Write-Host "[INFO]  Backend hazir olana kadar bekleniyor..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:8000/docs" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
        $ready = $true; break
    } catch {}
}
if ($ready) {
    Write-Host "[OK]    Backend hazir." -ForegroundColor Green
} else {
    Write-Host "[WARN]  Backend 15 saniyede yanit vermedi. Log: .backend.log" -ForegroundColor Yellow
}

# ── 7. Frontend baslat ────────────────────────────────────────────────────────
Write-Host "[INFO]  Frontend baslatiliyor (http://localhost:5174)..." -ForegroundColor Cyan
$frontendLog = "$ROOT\.frontend.log"
Start-Process powershell -ArgumentList `
    "-NoExit", "-Command",
    "Set-Location '$FRONTEND'; npm run dev 2>&1 | Tee-Object -FilePath '$frontendLog'" `
    -WindowStyle Minimized

Start-Sleep -Seconds 4

# ── 8. Tarayici ac ────────────────────────────────────────────────────────────
Write-Host "[INFO]  Tarayici aciliyor..." -ForegroundColor Cyan
Start-Process "http://localhost:5174"

Write-Host ""
Write-Host "[OK]    Sistem calisiyor!" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend  --> http://localhost:8000"
Write-Host "  Frontend --> http://localhost:5174"
Write-Host "  API Docs --> http://localhost:8000/docs"
Write-Host "  Loglar   --> .backend.log  .frontend.log"
Write-Host ""
Write-Host "Sistemi durdurmak icin bu pencereyi kapatin veya"
Write-Host "Gorev Yoneticisi'nden PowerShell pencerelerini kapatin."
Write-Host ""
Read-Host "Cikis icin Enter'a basin"
