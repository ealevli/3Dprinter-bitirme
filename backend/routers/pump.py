"""
Pump router.

Endpoints:
  POST /pump/start    → start pump at given RPM
  POST /pump/stop     → stop pump
  POST /pump/speed    → change speed while running
  GET  /pump/status   → current running state + RPM
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from services.pump_serial import pump_serial

router = APIRouter()


class SpeedRequest(BaseModel):
    rpm: int


def _ensure_connected() -> None:
    if not pump_serial.is_connected:
        ok = pump_serial.connect()
        if not ok:
            raise HTTPException(
                status_code=503,
                detail="Arduino'ya bağlanılamadı. Port ayarlarını kontrol edin.",
            )


@router.post("/connect")
async def connect():
    """Explicitly open the serial connection to the Arduino pump controller."""
    if pump_serial.is_connected:
        return {"message": "Arduino zaten bağlı.", "connected": True}
    ok = pump_serial.connect()
    if not ok:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Arduino'ya bağlanılamadı (port: {config.PUMP_PORT}). "
                "Ayarlar sayfasından doğru portu seçip kaydedin."
            ),
        )
    return {"message": f"Arduino bağlandı ({config.PUMP_PORT}).", "connected": True}


@router.post("/disconnect")
async def disconnect():
    """Close the serial connection to the Arduino."""
    pump_serial.disconnect()
    return {"message": "Arduino bağlantısı kesildi.", "connected": False}


@router.post("/start")
async def start(req: SpeedRequest):
    _ensure_connected()
    ok = pump_serial.start(req.rpm)
    if not ok:
        raise HTTPException(status_code=500, detail="Pompa başlatılamadı.")
    return {"message": f"Pompa başlatıldı ({req.rpm} RPM)."}


@router.post("/stop")
async def stop():
    _ensure_connected()
    ok = pump_serial.stop()
    if not ok:
        raise HTTPException(status_code=500, detail="Pompa durdurulamadı.")
    return {"message": "Pompa durduruldu."}


@router.post("/speed")
async def speed(req: SpeedRequest):
    _ensure_connected()
    ok = pump_serial.set_speed(req.rpm)
    if not ok:
        raise HTTPException(status_code=500, detail="Hız değiştirilemedi.")
    return {"message": f"Hız {req.rpm} RPM olarak ayarlandı."}


@router.get("/status")
async def status():
    if not pump_serial.is_connected:
        return {"running": False, "rpm": 0, "connected": False}
    return {**pump_serial.get_status(), "connected": True}
