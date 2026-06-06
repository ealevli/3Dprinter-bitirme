"""
Jog router — manual printer movement controls.

Endpoints:
  POST /jog/move        → relative axis move (X, Y, or Z)
  POST /jog/home        → G28 (home selected axes or all)
  POST /jog/send        → send arbitrary single G-code line
  POST /jog/babystep    → M290 Z delta (live offset tweak)
  POST /jog/set_surface → G92 Z0 (declare current position as surface)
"""

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from services.printer_serial import printer_serial

log = logging.getLogger(__name__)
router = APIRouter()


# ── Request models ────────────────────────────────────────────────────────────

class MoveRequest(BaseModel):
    axis: Literal["X", "Y", "Z"]
    distance: float
    feed_rate: int = 3000


class HomeRequest(BaseModel):
    axes: list[Literal["X", "Y", "Z"]] = ["X", "Y", "Z"]


class RawRequest(BaseModel):
    command: str


class BabystepRequest(BaseModel):
    delta: float   # mm — positive = up, negative = down


# ── Helper ────────────────────────────────────────────────────────────────────

def _require_connection():
    if not printer_serial.is_connected:
        raise HTTPException(
            status_code=503,
            detail="Yazıcı bağlı değil. Ayarlar → Yazıcıya Bağlan & Test Et.",
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/move")
async def jog_move(req: MoveRequest):
    log.info("[jog] POST /jog/move  axis=%s  dist=%s  feed=%s", req.axis, req.distance, req.feed_rate)
    _require_connection()

    feed = req.feed_rate
    dist = req.distance

    # G91 = relative mode, move, G90 = back to absolute
    for line, t in [
        ("G91", 5),
        (f"G0 F{feed} {req.axis}{dist:.3f}", 15),
        ("G90", 5),
    ]:
        log.debug("[jog] sending: %r  timeout=%ds", line, t)
        ok = await asyncio.to_thread(printer_serial.send_line, line, t)
        if not ok:
            # Always restore absolute mode even if move failed
            await asyncio.to_thread(printer_serial.send_line, "G90", 5)
            err = printer_serial._last_error
            log.error("[jog] move failed on %r: %s", line, err)
            raise HTTPException(status_code=500, detail=f"Hareket hatası: {err}")

    log.info("[jog] move OK: %s%+.3f mm", req.axis, dist)
    return {"message": f"{req.axis}{dist:+.2f} mm"}


@router.post("/home")
async def jog_home(req: HomeRequest):
    axes_str = " ".join(req.axes)
    log.info("[jog] POST /jog/home  axes=%s", axes_str)
    _require_connection()

    ok = await asyncio.to_thread(printer_serial.send_line, f"G28 {axes_str}", 120)
    if not ok:
        err = printer_serial._last_error
        log.error("[jog] home failed: %s", err)
        raise HTTPException(status_code=500, detail=f"Home hatası: {err}")

    log.info("[jog] home OK: %s", axes_str)
    return {"message": f"{axes_str} home tamamlandı."}


@router.post("/send")
async def jog_send(req: RawRequest):
    cmd = req.command.strip()
    log.info("[jog] POST /jog/send  cmd=%r", cmd)
    _require_connection()

    if not cmd:
        raise HTTPException(status_code=400, detail="Komut boş olamaz.")

    ok = await asyncio.to_thread(printer_serial.send_line, cmd, 30)
    if not ok:
        err = printer_serial._last_error
        log.error("[jog] send failed: %s", err)
        raise HTTPException(status_code=500, detail=f"Komut hatası: {err}")

    log.info("[jog] send OK: %r", cmd)
    return {"message": f"Gönderildi: {cmd}"}


@router.post("/babystep")
async def jog_babystep(req: BabystepRequest):
    """Adjust Z by a tiny amount using M290 (live babystep, no homing needed)."""
    delta = round(req.delta, 3)
    log.info("[jog] POST /jog/babystep  delta=%s", delta)
    _require_connection()

    ok = await asyncio.to_thread(printer_serial.send_line, f"M290 Z{delta}", 5)
    if not ok:
        err = printer_serial._last_error
        log.error("[jog] babystep failed: %s", err)
        raise HTTPException(status_code=500, detail=f"Babystep hatası: {err}")

    log.info("[jog] babystep OK: %+.3f mm", delta)
    return {"message": f"Z babystep: {delta:+.3f} mm"}


@router.post("/set_surface")
async def jog_set_surface():
    """
    Declare the nozzle's current position as Z=0 (part surface).
    Use after manually jogging until nozzle just touches the part.
    """
    log.info("[jog] POST /jog/set_surface")
    _require_connection()

    ok = await asyncio.to_thread(printer_serial.send_line, "G92 Z0", 5)
    if not ok:
        err = printer_serial._last_error
        log.error("[jog] set_surface failed: %s", err)
        raise HTTPException(status_code=500, detail=f"G92 hatası: {err}")

    log.info("[jog] set_surface OK")
    return {"message": "Mevcut konum Z=0 (yüzey) olarak ayarlandı."}
