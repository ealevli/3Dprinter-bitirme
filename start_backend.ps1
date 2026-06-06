$ROOT    = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV    = "$ROOT\.venv"
$BACKEND = "$ROOT\backend"

Write-Host "Backend baslatiliyor (auto-restart aktif)..." -ForegroundColor Cyan

& "$VENV\Scripts\activate.ps1"
Set-Location $BACKEND

while ($true) {
    $start = Get-Date
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    $elapsed = ((Get-Date) - $start).TotalSeconds
    if ($elapsed -lt 5) {
        Write-Host "Backend cok hizli cakti ($([math]::Round($elapsed,1))s). Baslatma durduruldu." -ForegroundColor Red
        break
    }
    Write-Host "Backend cakti, 2 saniye sonra yeniden baslatiliyor..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
}
