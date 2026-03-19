#!/usr/bin/env bash
# start.sh — macOS / Linux startup script for the Coating System
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║    3D Yazıcı Kaplama Sistemi — Başlatıcı ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Python check ───────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    error "Python 3 bulunamadı. Lütfen Python 3.10+ yükleyin."
    exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python $PY_VER bulundu."

# ── 2. Virtual environment ────────────────────────────────────────────────────
VENV="$ROOT/.venv"
if [ ! -d "$VENV" ]; then
    info "Sanal ortam oluşturuluyor (.venv)…"
    python3 -m venv "$VENV"
    success "Sanal ortam oluşturuldu."
fi

source "$VENV/bin/activate"

# ── 3. Python dependencies ────────────────────────────────────────────────────
info "Python bağımlılıkları kontrol ediliyor…"
pip install -q --upgrade pip
pip install -q -r "$ROOT/requirements.txt"
success "Python bağımlılıkları hazır."

# ── 4. Node / npm check ───────────────────────────────────────────────────────
if ! command -v npm &>/dev/null; then
    error "npm bulunamadı. Lütfen Node.js 18+ yükleyin: https://nodejs.org"
    exit 1
fi
info "Node $(node --version) / npm $(npm --version) bulundu."

# ── 5. Frontend dependencies ──────────────────────────────────────────────────
if [ ! -d "$FRONTEND/node_modules" ]; then
    info "npm install çalıştırılıyor…"
    npm --prefix "$FRONTEND" install --silent
    success "Frontend bağımlılıkları hazır."
else
    info "node_modules mevcut, atlanıyor."
fi

# ── 6. Launch backend ─────────────────────────────────────────────────────────
info "Backend başlatılıyor (http://localhost:8000)…"
cd "$BACKEND"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd "$ROOT"

# ── 7. Launch frontend ────────────────────────────────────────────────────────
sleep 1
info "Frontend başlatılıyor (http://localhost:5173)…"
npm --prefix "$FRONTEND" run dev &
FRONTEND_PID=$!

echo ""
success "Sistem çalışıyor!"
echo -e "  Backend  → ${CYAN}http://localhost:8000${NC}"
echo -e "  Frontend → ${CYAN}http://localhost:5173${NC}"
echo -e "  API Docs → ${CYAN}http://localhost:8000/docs${NC}"
echo ""
echo "Durdurmak için Ctrl+C tuşlayın."
echo ""

# ── 8. Shutdown hook ──────────────────────────────────────────────────────────
cleanup() {
    echo ""
    info "Kapatılıyor…"
    kill "$BACKEND_PID"  2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    deactivate 2>/dev/null || true
    success "Sistem durduruldu."
}
trap cleanup INT TERM

wait "$BACKEND_PID" "$FRONTEND_PID"
