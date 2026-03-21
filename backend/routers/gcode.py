"""
G-code router.

Endpoints:
  POST /gcode/generate   → contour + params → gcode string
  POST /gcode/preview    → gcode → canvas paths
  POST /gcode/send       → start sending gcode to printer (async)
  GET  /gcode/status     → current job status
  POST /gcode/stop       → emergency stop
"""

import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from services.gcode_generator import (
    generate_gcode,
    CoatingParams,
    DEFAULT_START_GCODE,
    DEFAULT_END_GCODE,
)
from services.printer_serial import printer_serial

router = APIRouter()


class GenerateRequest(BaseModel):
    contour_mm: list[list[float]]
    line_spacing: float = 1.0
    z_offset: float = 0.3
    feed_rate: int = 600
    travel_rate: int = 1500
    band_thickness: float = 1.0
    pattern_type: str = "zigzag"
    start_gcode: str | None = None
    end_gcode: str | None = None


class SendRequest(BaseModel):
    gcode: str


@router.get("/defaults")
async def get_defaults():
    """Return the default start and end G-code sequences."""
    return {
        "start_gcode": DEFAULT_START_GCODE,
        "end_gcode": DEFAULT_END_GCODE,
    }


@router.post("/generate")
async def generate(req: GenerateRequest):
    """Generate G-code from contour_mm and coating parameters."""
    if not req.contour_mm:
        raise HTTPException(status_code=400, detail="contour_mm boş olamaz.")
    params = CoatingParams(
        line_spacing=req.line_spacing,
        z_offset=req.z_offset,
        feed_rate=req.feed_rate,
        travel_rate=req.travel_rate,
        band_thickness=req.band_thickness,
        pattern_type=req.pattern_type,  # type: ignore[arg-type]
    )
    return generate_gcode(req.contour_mm, params, req.start_gcode, req.end_gcode)


@router.post("/preview")
async def preview(req: SendRequest):
    """Parse G-code and return XY paths for canvas rendering."""
    paths: list[dict] = []
    for line in req.gcode.splitlines():
        parts_map: dict[str, float] = {}
        for token in line.strip().split():
            if token and token[0] in "XYZF" and len(token) > 1:
                try:
                    parts_map[token[0]] = float(token[1:])
                except ValueError:
                    pass
        if "X" in parts_map and "Y" in parts_map:
            paths.append({"x": parts_map["X"], "y": parts_map["Y"]})
    return {"paths": paths}


@router.post("/send")
async def send(req: SendRequest):
    """Begin sending G-code to the printer in a background thread."""
    if not printer_serial.is_connected:
        ok = printer_serial.connect()
        if not ok:
            raise HTTPException(
                status_code=503,
                detail="Yazıcıya bağlanılamadı. Port ayarlarını kontrol edin.",
            )
    job_id = str(uuid.uuid4())[:8]
    printer_serial.send_gcode(req.gcode, job_id)
    return {"job_id": job_id, "message": "G-code gönderimi başladı."}


@router.get("/status")
async def status():
    """Return the current G-code job status."""
    return printer_serial.get_status()


@router.post("/stop")
async def stop():
    """Send M112 emergency stop and abort the current job."""
    printer_serial.emergency_stop()
    return {"message": "Durdurma komutu gönderildi (M112)."}
