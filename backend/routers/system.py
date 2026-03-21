"""
System router — port discovery, connection status, config update.

Endpoints:
  GET  /system/ports    → list available serial ports
  GET  /system/status   → camera / printer / pump connection status
  POST /system/config   → update runtime config (ports, baudrate, ArUco positions…)
"""

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


@router.get("/ports")
async def list_ports():
    """Return all detected serial ports on the host machine."""
    ports = [
        {"device": p.device, "description": p.description}
        for p in serial.tools.list_ports.comports()
    ]
    return {"ports": ports}


@router.get("/status")
async def status():
    """Return connection status of camera, printer, and pump."""
    calibration_ready = load_calibration() is not None
    return {
        "camera": "ok" if camera_service.is_open else "disconnected",
        "printer": "ok" if printer_serial.is_connected else "disconnected",
        "pump": "ok" if pump_serial.is_connected else "disconnected",
        "calibration": "ok" if calibration_ready else "required",
    }


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

    return {"message": "Ayarlar güncellendi.", "applied": list(updates.keys())}
