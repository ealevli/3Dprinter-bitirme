"""
System router — port discovery, connection status, config update.

Endpoints:
  GET  /system/ports    → list available serial ports
  GET  /system/status   → camera / printer / pump connection status
  POST /system/config   → update runtime config (ports, baudrate, ArUco positions…)
"""

import asyncio
import json
import os
from typing import Any

from fastapi import APIRouter, HTTPException
import serial.tools.list_ports

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from services.camera_service import camera_service
from services.printer_serial import printer_serial
from services.pump_serial import pump_serial
from services.calibration import load_calibration

router = APIRouter()


@router.get("/config")
async def get_config():
    """Return the current runtime configuration."""
    return {
        "printer_port": config.PRINTER_PORT,
        "printer_baudrate": config.PRINTER_BAUDRATE,
        "pump_port": config.PUMP_PORT,
        "pump_baudrate": config.PUMP_BAUDRATE,
        "camera_index": config.CAMERA_INDEX,
        "aruco_marker_positions_mm": {
            str(k): list(v)
            for k, v in config.ARUCO_MARKER_POSITIONS_MM.items()
        },
    }


def _port_hint(p) -> str:
    """Classify a serial port so the UI can warn about wrong selections."""
    desc = (p.description or "").lower()
    hwid = (p.hwid or "").lower()
    mfr  = (p.manufacturer or "").lower()

    if "bluetooth" in desc or "bluetooth" in mfr or "bthmodem" in hwid:
        return "bluetooth"   # Never an Arduino over USB

    # Common USB-Serial chips used by Arduinos and Ender-3 alike
    arduino_chips = ("ch340", "ch341", "cp210", "ftdi", "ft232", "arduino")
    if any(chip in desc or chip in hwid or chip in mfr for chip in arduino_chips):
        return "usb_serial"  # Likely a real Arduino or printer

    return "unknown"


@router.get("/calibration_debug")
async def calibration_debug():
    """Return calibration matrix + config marker positions for debugging 0×0 mm issues."""
    from services.calibration import load_calibration, pixel_to_mm
    import numpy as np
    H = load_calibration()
    if H is None:
        return {"calibrated": False, "message": "calibration.json bulunamadı"}
    # Test: map a grid of points to see if H is sane
    test_pts = [(100, 100), (320, 240), (500, 350), (640, 480)]
    mapped = []
    for px, py in test_pts:
        mx, my = pixel_to_mm(px, py, H)
        mapped.append({"px": px, "py": py, "mm_x": round(mx, 2), "mm_y": round(my, 2)})
    return {
        "calibrated": True,
        "H": H.tolist(),
        "marker_positions_mm": {str(k): v for k, v in config.ARUCO_MARKER_POSITIONS_MM.items()},
        "test_mapping": mapped,
    }


@router.get("/ports")
async def list_ports():
    """Return all detected serial ports with type hints to aid port selection."""
    ports = []
    for p in serial.tools.list_ports.comports():
        hint = _port_hint(p)
        ports.append({
            "device": p.device,
            "description": p.description,
            "hint": hint,
            # Bluetooth ports almost never work as Arduino; flag them
            "warning": "Bluetooth portu — Arduino için kullanmayın" if hint == "bluetooth" else None,
        })
    return {"ports": ports}


@router.get("/status")
async def status():
    """Return connection status of camera, printer, and pump."""
    import asyncio
    calibration_ready = load_calibration() is not None

    # Verify pump connection — guard with a timeout so a hung Arduino can't
    # freeze the status page.
    if pump_serial.is_connected:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(pump_serial.get_status),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            pass
    pump_ok = pump_serial.is_connected

    return {
        "camera": "ok" if camera_service.is_open else "disconnected",
        "printer": "ok" if printer_serial.is_connected else "disconnected",
        "pump": "ok" if pump_ok else "disconnected",
        "calibration": "ok" if calibration_ready else "required",
    }


@router.post("/connect_printer")
async def connect_printer():
    """Disconnect and reconnect the printer using the current config port."""
    await asyncio.to_thread(printer_serial.disconnect)
    ok = await asyncio.to_thread(printer_serial.connect)
    if not ok:
        raise HTTPException(
            status_code=503,
            detail=f"Yazıcıya bağlanılamadı: {config.PRINTER_PORT}. Port ve baud rate'i kontrol edin.",
        )
    return {"message": f"{config.PRINTER_PORT} portuna bağlandı."}


@router.post("/config")
async def update_config(updates: dict[str, Any]):
    """
    Update runtime configuration values.

    Accepted keys (examples):
      printer_port, printer_baudrate,
      pump_port, pump_baudrate,
      camera_index,
      aruco_marker_positions_mm  (dict: {"0": [x, y], …})
    """
    mapping = {
        "printer_port": "PRINTER_PORT",
        "printer_baudrate": "PRINTER_BAUDRATE",
        "pump_port": "PUMP_PORT",
        "pump_baudrate": "PUMP_BAUDRATE",
        "camera_index": "CAMERA_INDEX",
    }

    camera_index_changed = (
        "camera_index" in updates
        and updates["camera_index"] != config.CAMERA_INDEX
    )

    for key, value in updates.items():
        attr = mapping.get(key)
        if attr:
            setattr(config, attr, value)
        elif key == "aruco_marker_positions_mm":
            config.ARUCO_MARKER_POSITIONS_MM = {
                int(k): tuple(v) for k, v in value.items()
            }

    # If camera index changed, close current camera so it reopens with new index
    # on the next stream/capture request.
    if camera_index_changed:
        camera_service.close()

    # Persist to disk so settings survive server restarts
    config.save_user_config()

    return {"message": "Ayarlar güncellendi.", "applied": list(updates.keys())}
