"""
Jog router — manual printer movement controls.

Endpoints:
  POST /jog/move   → relative axis move (X, Y, or Z)
  POST /jog/home   → G28 (home selected axes or all)
  POST /jog/send   → send arbitrary single G-code line
"""

import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from services.printer_serial import printer_serial

router = APIRouter()


class MoveRequest(BaseModel):
    axis: Literal["X", "Y", "Z"]
    distance: float
    feed_rate: int = 3000


class HomeRequest(BaseModel):
    axes: list[Literal["X", "Y", "Z"]] = ["X", "Y", "Z"]


class RawRequest(BaseModel):
    command: str


def _require_connection():
    if not printer_serial.is_connected:
        raise HTTPException(status_code=503, detail="Yazıcı bağlı değil. Ayarlar → Yazıcıya Bağlan.")


def _send(line: str, timeout: float = 15.0) -> bool:
    return printer_serial.send_line(line, timeout_s=timeout)


@router.post("/move")
async def jog_move(req: MoveRequest):
    _require_connection()
    feed = req.feed_rate
    dist = req.distance

    # G91 = relative mode, move, G90 = back to absolute
    loop = asyncio.get_event_loop()
    for line, t in [("G91", 5), (f"G0 F{feed} {req.axis}{dist:.3f}", 15), ("G90", 5)]:
        ok = await loop.run_in_executor(None, lambda l=line, to=t: _send(l, to))
        if not ok:
            await loop.run_in_executor(None, lambda: _send("G90", 5))  # always restore absolute
            raise HTTPException(status_code=500, detail=f"Hareket hatası: {printer_serial._last_error}")

    return {"message": f"{req.axis}{dist:+.2f} mm"}


@router.post("/home")
async def jog_home(req: HomeRequest):
    _require_connection()
    axes_str = " ".join(req.axes)
    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(None, lambda: _send(f"G28 {axes_str}", 120))
    if not ok:
        raise HTTPException(status_code=500, detail=f"Home hatası: {printer_serial._last_error}")
    return {"message": f"{axes_str} home tamamlandı."}


@router.post("/send")
async def jog_send(req: RawRequest):
    _require_connection()
    cmd = req.command.strip()
    if not cmd:
        raise HTTPException(status_code=400, detail="Komut boş olamaz.")
    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(None, lambda: _send(cmd, 30))
    if not ok:
        raise HTTPException(status_code=500, detail=f"Komut hatası: {printer_serial._last_error}")
    return {"message": f"Gönderildi: {cmd}"}
