#!/usr/bin/env bash
# start.sh — macOS / Linux startup script for the Coating System
# NOT: set -e kaldırıldı; her adım kendi hatasını yakalar.

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$ROOT/.venv"

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()     { echo -e "${RED}[ERROR]${NC} $*"; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║    3D Yazıcı Kaplama Sistemi — Başlatıcı ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 0. Port temizliği (8000 ve 5174) ─────────────────────────────────────────
for PORT in 8000 5174; do
    PIDS=$(lsof -ti tcp:"$PORT" 2>/dev/null)
    if [ -n "$PIDS" ]; then
        warn "Port $PORT meşgul, temizleniyor… (PID: $PIDS)"
        kill -9 $PIDS 2>/dev/null || true
        sleep 0.5
    fi
done

# ── 1. Python check ───────────────────────────────────────────────────────────
PY_BIN=""
for candidate in python3 python3.12 python3.11 python3.10; do
    if command -v "$candidate" &>/dev/null; then
        PY_BIN="$candidate"
        break
    fi
done
if [ -z "$PY_BIN" ]; then
    err "Python 3 bulunamadı. Lütfen Python 3.10+ yükleyin."
    exit 1
fi
PY_VER=$("$PY_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python $PY_VER ($PY_BIN) bulundu."

# ── 2. Virtual environment ────────────────────────────────────────────────────
if [ ! -d "$VENV" ]; then
    info "Sanal ortam oluşturuluyor (.venv)…"
    "$PY_BIN" -m venv "$VENV"
    if [ $? -ne 0 ]; then
        err "Sanal ortam oluşturulamadı."
        exit 1
    fi
    success "Sanal ortam oluşturuldu."
fi

source "$VENV/bin/activate"

# ── 3. Python dependencies ────────────────────────────────────────────────────
info "Python bağımlılıkları kontrol ediliyor…"
pip install -q -r "$ROOT/requirements.txt"
if [ $? -ne 0 ]; then
    err "Bağımlılık yüklemesi başarısız. requirements.txt kontrol edin."
    exit 1
fi
success "Python bağımlılıkları hazır."

# ── 4. Node / npm check ───────────────────────────────────────────────────────
if ! command -v npm &>/dev/null; then
    err "npm bulunamadı. Lütfen Node.js 18+ yükleyin: https://nodejs.org"
    exit 1
fi
info "Node $(node --version) / npm $(npm --version) bulundu."

# ── 5. Frontend dependencies ──────────────────────────────────────────────────
# node_modules'ün bu platformda kurulduğunu kontrol et (rollup native binding)
NEEDS_INSTALL=false
if [ ! -d "$FRONTEND/node_modules" ]; then
    NEEDS_INSTALL=true
elif ! node -e "require('$FRONTEND/node_modules/rollup/dist/native.js')" &>/dev/null 2>&1; then
    warn "node_modules farklı platformda kurulmuş, yeniden yükleniyor…"
    rm -rf "$FRONTEND/node_modules" "$FRONTEND/package-lock.json"
    NEEDS_INSTALL=true
fi

if [ "$NEEDS_INSTALL" = true ]; then
    info "npm install çalıştırılıyor…"
    npm --prefix "$FRONTEND" install --silent
    if [ $? -ne 0 ]; then
        err "Frontend bağımlılıkları yüklenemedi."
        exit 1
    fi
    success "Frontend bağımlılıkları hazır."
else
    info "node_modules hazır."
fi

# ── 6. Backend başlat ─────────────────────────────────────────────────────────
info "Backend başlatılıyor (http://localhost:8000)…"
cd "$BACKEND"
"$VENV/bin/python" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload \
    --reload-exclude "*.pyc" --reload-exclude "__pycache__" \
    > "$ROOT/.backend.log" 2>&1 &
BACKEND_PID=$!
cd "$ROOT"

# Backend'in ayağa kalkmasını bekle
info "Backend hazır olana kadar bekleniyor…"
for i in $(seq 1 15); do
    if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
        success "Backend hazır."
        break
    fi
    sleep 1
    if [ $i -eq 15 ]; then
        warn "Backend 15 saniyede yanıt vermedi. Loglar: .backend.log"
    fi
done

# ── 7. Frontend başlat ────────────────────────────────────────────────────────
info "Frontend başlatılıyor (http://localhost:5174)…"
npm --prefix "$FRONTEND" run dev > "$ROOT/.frontend.log" 2>&1 &
FRONTEND_PID=$!

# Frontend'in ayağa kalkmasını bekle
for i in $(seq 1 10); do
    if curl -s http://localhost:5174 > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# ── 8. Tarayıcı aç ───────────────────────────────────────────────────────────
sleep 1
if command -v open &>/dev/null; then
    # macOS
    open http://localhost:5174
elif command -v xdg-open &>/dev/null; then
    # Linux
    xdg-open http://localhost:5174
fi

echo ""
success "Sistem çalışıyor!"
echo -e "  Backend  → ${CYAN}http://localhost:8000${NC}"
echo -e "  Frontend → ${CYAN}http://localhost:5174${NC}"
echo -e "  API Docs → ${CYAN}http://localhost:8000/docs${NC}"
echo -e "  Loglar   → ${CYAN}.backend.log  .frontend.log${NC}"
echo ""
echo "Durdurmak için Ctrl+C tuşlayın."
echo ""

# ── 9. Shutdown hook ──────────────────────────────────────────────────────────
cleanup() {
    echo ""
    info "Kapatılıyor…"
    kill "$BACKEND_PID"  2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    deactivate 2>/dev/null || true
    success "Sistem durduruldu."
    exit 0
}
trap cleanup INT TERM

wait "$BACKEND_PID" "$FRONTEND_PID"
