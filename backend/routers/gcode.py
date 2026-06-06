"""
G-code router.

Endpoints:
  POST /gcode/generate   → contour + params → gcode string
  POST /gcode/preview    → gcode → canvas paths
  POST /gcode/send       → start sending gcode to printer (async)
  GET  /gcode/status     → current job status
  POST /gcode/stop       → emergency stop
"""

import asyncio
import logging
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
    POST_PROBE_START_GCODE,
)
from services.printer_serial import printer_serial

log = logging.getLogger(__name__)

router = APIRouter()


class GenerateRequest(BaseModel):
    contour_mm: list[list[float]]
    line_spacing: float = 1.0
    z_offset: float = 0.3
    feed_rate: int = 600
    travel_rate: int = 1500
    band_thickness: float = 1.0
    pattern_type: str = "zigzag"
    x_offset_mm: float = 0.0      # XY correction: add to all X coords
    y_offset_mm: float = 0.0      # XY correction: add to all Y coords
    contour_inset_mm: float = 0.0   # shrink polygon inward (stay on-part, avoid tape)
    manual_width_mm: float = 0.0   # override: use exact rectangle (0 = use detection)
    manual_height_mm: float = 0.0  # override: use exact rectangle (0 = use detection)
    start_gcode: str | None = None
    end_gcode: str | None = None


class SendRequest(BaseModel):
    gcode: str


class ProbeAndSendRequest(BaseModel):
    """Request body for /gcode/probe_and_send — full automated BLTouch Z flow."""
    contour_mm: list[list[float]]
    line_spacing: float = 1.0
    z_offset: float = 0.3       # gap above the BLTouch-probed surface (mm)
    feed_rate: int = 600
    travel_rate: int = 1500
    band_thickness: float = 1.0
    pattern_type: str = "zigzag"
    x_offset_mm: float = 0.0
    y_offset_mm: float = 0.0
    contour_inset_mm: float = 0.0
    manual_width_mm: float = 0.0
    manual_height_mm: float = 0.0


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
        x_offset_mm=req.x_offset_mm,
        y_offset_mm=req.y_offset_mm,
        contour_inset_mm=req.contour_inset_mm,
        manual_width_mm=req.manual_width_mm,
        manual_height_mm=req.manual_height_mm,
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
        ok = await asyncio.to_thread(printer_serial.connect)
        if not ok:
            raise HTTPException(
                status_code=503,
                detail="Yazıcıya bağlanılamadı. Ayarlar sayfasından yazıcı portunu seçip bağlanın.",
            )
    job_id = str(uuid.uuid4())[:8]
    printer_serial.send_gcode(req.gcode, job_id)
    return {"job_id": job_id, "message": "G-code gönderimi başladı.", "total_lines": printer_serial._total_lines}


@router.post("/probe_and_send")
async def probe_and_send(req: ProbeAndSendRequest):
    """
    Full automated BLTouch Z-probe + coating flow:

    1. Connect to printer (auto if not connected)
    2. G28  — home all axes (BLTouch establishes Z reference)
    3. G0   — move to part centroid XY at safe Z
    4. G30  — BLTouch probes the actual part surface, reads Z value
    5. Generate G-code with z_coat = probed_z + z_offset
    6. Send G-code to printer in background

    The z_offset parameter is the gap above the probed surface in mm (0.2-0.5 typical).
    band_thickness is NOT used — BLTouch measures the surface directly (tape included).
    """
    if not printer_serial.is_connected:
        ok = await asyncio.to_thread(printer_serial.connect)
        if not ok:
            raise HTTPException(
                status_code=503,
                detail="Yaziciya baglanilmadi. Ayarlar sayfasindan portu secin.",
            )

    # ── Compute centroid (mirrors generate_gcode logic) ──────────────────
    from shapely.geometry import Polygon

    contour = req.contour_mm
    if req.x_offset_mm or req.y_offset_mm:
        contour = [[p[0] + req.x_offset_mm, p[1] + req.y_offset_mm] for p in contour]

    poly = Polygon([(p[0], p[1]) for p in contour])
    if not poly.is_valid:
        poly = poly.buffer(0)

    if req.manual_width_mm > 0 and req.manual_height_mm > 0:
        cx0, cy0 = poly.centroid.x, poly.centroid.y
        hw, hh = req.manual_width_mm / 2, req.manual_height_mm / 2
        poly = Polygon([
            (cx0 - hw, cy0 - hh), (cx0 + hw, cy0 - hh),
            (cx0 + hw, cy0 + hh), (cx0 - hw, cy0 + hh),
        ])

    if req.contour_inset_mm > 0:
        shrunk = poly.buffer(-req.contour_inset_mm)
        if not shrunk.is_empty and shrunk.area > 1.0:
            poly = shrunk

    cx = round(poly.centroid.x, 3)
    cy = round(poly.centroid.y, 3)
    log.info("[probe_and_send] centroid X=%.3f Y=%.3f", cx, cy)

    # ── 1. Home ──────────────────────────────────────────────────────────
    log.info("[probe_and_send] G28 homing...")
    ok = await asyncio.to_thread(printer_serial.send_line, "G28")
    if not ok:
        raise HTTPException(status_code=500, detail="G28 homing basarisiz.")

    # ── 2. Safe Z, then move to part center XY ───────────────────────────
    await asyncio.to_thread(printer_serial.send_line, f"G0 F{req.travel_rate} Z15")
    await asyncio.to_thread(printer_serial.send_line,
                            f"G0 F{req.travel_rate} X{cx:.3f} Y{cy:.3f}")

    # ── 3. BLTouch probe at part center ──────────────────────────────────
    log.info("[probe_and_send] probing surface at X=%.3f Y=%.3f", cx, cy)
    probed_z = await asyncio.to_thread(printer_serial.probe_z, cx, cy)
    log.info("[probe_and_send] probed_z = %s", probed_z)

    # ── 4. Generate G-code with probed Z ─────────────────────────────────
    params = CoatingParams(
        line_spacing=req.line_spacing,
        z_offset=req.z_offset,
        feed_rate=req.feed_rate,
        travel_rate=req.travel_rate,
        band_thickness=req.band_thickness,
        pattern_type=req.pattern_type,       # type: ignore[arg-type]
        x_offset_mm=req.x_offset_mm,
        y_offset_mm=req.y_offset_mm,
        contour_inset_mm=req.contour_inset_mm,
        manual_width_mm=req.manual_width_mm,
        manual_height_mm=req.manual_height_mm,
        probed_z=probed_z,
    )
    result = generate_gcode(req.contour_mm, params, start_gcode=POST_PROBE_START_GCODE)

    # ── 5. Send ───────────────────────────────────────────────────────────
    job_id = str(uuid.uuid4())[:8]
    printer_serial.send_gcode(result["gcode"], job_id)

    z_actual = round(probed_z + req.z_offset, 3) if probed_z is not None else None
    if probed_z is not None:
        z_msg = f"BLTouch Z={probed_z:.3f} mm -> kaplama Z={z_actual:.3f} mm"
    else:
        z_msg = "BLTouch probe basarisiz — varsayilan Z kullaniliyor"

    return {
        "job_id": job_id,
        "message": f"Gonderim basladi. {z_msg}",
        "probed_z": probed_z,
        "z_coat": z_actual,
        "pump_start_line": result["pump_start_line"],
        "total_lines": printer_serial._total_lines,
    }


@router.get("/status")
async def status():
    """Return the current G-code job status."""
    return printer_serial.get_status()


@router.post("/stop")
async def stop():
    """Send M112 emergency stop and abort the current job."""
    printer_serial.emergency_stop()
    return {"message": "Durdurma komutu gönderildi (M112)."}
