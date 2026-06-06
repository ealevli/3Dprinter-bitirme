"""
Pump router.

Every blocking call is wrapped in asyncio.wait_for so a hung Arduino can
never freeze the FastAPI event loop.  Timeouts are generous but finite:

  connect   → 10 s  (port open + 1.5 s Arduino boot)
  start     →  8 s  (two serial round-trips: SPEED + START, 3 s each + margin)
  stop      →  5 s
  speed     →  5 s
  direction →  5 s
  prime     →  5 s
  status    →  5 s

Endpoints:
  POST /pump/connect
  POST /pump/disconnect
  POST /pump/start
  POST /pump/stop
  POST /pump/speed
  POST /pump/direction
  POST /pump/prime
  GET  /pump/status
"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from services.pump_serial import pump_serial

log = logging.getLogger(__name__)
router = APIRouter()


# ── Request models ────────────────────────────────────────────────────────────

class SpeedRequest(BaseModel):
    rpm: int

class DirectionRequest(BaseModel):
    forward: bool

class PrimeRequest(BaseModel):
    steps: int


# ── Helper ────────────────────────────────────────────────────────────────────

def _timeout_error(endpoint: str, port: str) -> HTTPException:
    return HTTPException(
        status_code=504,
        detail=(
            f"{endpoint}: zaman aşımı (port: {port}). "
            "Arduino bağlı ve doğru porta mı takılı?"
        ),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/connect")
async def connect():
    """Explicitly open the serial connection to the Arduino pump controller."""
    log.info("[pump router] POST /pump/connect  port=%s", config.PUMP_PORT)

    if pump_serial.is_connected:
        return {"message": "Arduino zaten bağlı.", "connected": True}

    try:
        ok = await asyncio.wait_for(
            asyncio.to_thread(pump_serial.connect),
            timeout=10.0,
        )
    except asyncio.TimeoutError:
        raise _timeout_error("/pump/connect", config.PUMP_PORT)

    if not ok:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Arduino'ya bağlanılamadı (port: {config.PUMP_PORT}). "
                f"Hata: {pump_serial.last_error or 'bilinmiyor'}. "
                "Ayarlar sayfasından doğru portu seçip kaydedin."
            ),
        )
    return {"message": f"Arduino bağlandı ({config.PUMP_PORT}).", "connected": True}


@router.post("/disconnect")
async def disconnect():
    """Close the serial connection to the Arduino."""
    log.info("[pump router] POST /pump/disconnect")
    await asyncio.to_thread(pump_serial.disconnect)
    return {"message": "Arduino bağlantısı kesildi.", "connected": False}


@router.post("/start")
async def start(req: SpeedRequest):
    log.info("[pump router] POST /pump/start  rpm=%d", req.rpm)
    if not pump_serial.is_connected:
        raise HTTPException(status_code=503, detail="Arduino bağlı değil.")
    try:
        ok = await asyncio.wait_for(
            asyncio.to_thread(pump_serial.start, req.rpm),
            timeout=8.0,
        )
    except asyncio.TimeoutError:
        raise _timeout_error("/pump/start", config.PUMP_PORT)
    if not ok:
        raise HTTPException(
            status_code=500,
            detail=f"Pompa başlatılamadı: {pump_serial.last_error or 'Arduino cevap vermedi'}",
        )
    return {"message": f"Pompa başlatıldı ({req.rpm} adım/s)."}


@router.post("/stop")
async def stop():
    log.info("[pump router] POST /pump/stop")
    if not pump_serial.is_connected:
        raise HTTPException(status_code=503, detail="Arduino bağlı değil.")
    try:
        ok = await asyncio.wait_for(
            asyncio.to_thread(pump_serial.stop),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        raise _timeout_error("/pump/stop", config.PUMP_PORT)
    if not ok:
        raise HTTPException(
            status_code=500,
            detail=f"Pompa durdurulamadı: {pump_serial.last_error or 'Arduino cevap vermedi'}",
        )
    return {"message": "Pompa durduruldu."}


@router.post("/speed")
async def speed(req: SpeedRequest):
    log.info("[pump router] POST /pump/speed  rpm=%d", req.rpm)
    if not pump_serial.is_connected:
        raise HTTPException(status_code=503, detail="Arduino bağlı değil.")
    try:
        ok = await asyncio.wait_for(
            asyncio.to_thread(pump_serial.set_speed, req.rpm),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        raise _timeout_error("/pump/speed", config.PUMP_PORT)
    if not ok:
        raise HTTPException(
            status_code=500,
            detail=f"Hız değiştirilemedi: {pump_serial.last_error or 'Arduino cevap vermedi'}",
        )
    return {"message": f"Hız {req.rpm} adım/s olarak ayarlandı."}


@router.post("/direction")
async def direction(req: DirectionRequest):
    log.info("[pump router] POST /pump/direction  forward=%s", req.forward)
    if not pump_serial.is_connected:
        raise HTTPException(status_code=503, detail="Arduino bağlı değil.")
    try:
        ok = await asyncio.wait_for(
            asyncio.to_thread(pump_serial.set_direction, req.forward),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        raise _timeout_error("/pump/direction", config.PUMP_PORT)
    if not ok:
        raise HTTPException(
            status_code=500,
            detail=f"Yön değiştirilemedi: {pump_serial.last_error or 'Arduino cevap vermedi'}",
        )
    label = "ileri (kaplama)" if req.forward else "geri (geri çekme)"
    return {"message": f"Yön {label} olarak ayarlandı."}


@router.post("/prime")
async def prime(req: PrimeRequest):
    log.info("[pump router] POST /pump/prime  steps=%d", req.steps)
    if not pump_serial.is_connected:
        raise HTTPException(status_code=503, detail="Arduino bağlı değil.")
    if req.steps <= 0:
        raise HTTPException(status_code=400, detail="steps > 0 olmalı.")
    try:
        ok = await asyncio.wait_for(
            asyncio.to_thread(pump_serial.prime, req.steps),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        raise _timeout_error("/pump/prime", config.PUMP_PORT)
    if not ok:
        raise HTTPException(
            status_code=500,
            detail=f"Prime başlatılamadı: {pump_serial.last_error or 'Arduino cevap vermedi'}",
        )
    return {"message": f"Prime başlatıldı ({req.steps} adım)."}


@router.get("/status")
async def status():
    if not pump_serial.is_connected:
        return {"running": False, "rpm": 0, "direction": "fwd", "connected": False}
    try:
        data = await asyncio.wait_for(
            asyncio.to_thread(pump_serial.get_status),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        # Return cached state rather than an error — the UI keeps working
        log.warning("[pump router] GET /pump/status timed out — returning cached state")
        return {"running": False, "rpm": 0, "direction": "fwd", "connected": True, "timeout": True}
    connected = pump_serial.is_connected
    return {**data, "connected": connected}
