"""
Camera router.

Endpoints:
  GET  /camera/stream     → MJPEG video stream
  POST /camera/capture    → single JPEG frame (base64)
  POST /camera/calibrate  → ArUco calibration
"""

import base64
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from services.camera_service import camera_service
from services.calibration import run_calibration

router = APIRouter()


def _ensure_camera() -> None:
    """Open the camera if it is not already open; raise 503 on failure."""
    if not camera_service.is_open:
        ok = camera_service.open()
        if not ok:
            raise HTTPException(
                status_code=503,
                detail="Kamera açılamadı. Cihazın bağlı olduğundan emin olun.",
            )


@router.get("/stream")
async def stream():
    """MJPEG stream — use as <img src='/camera/stream'> in the frontend."""
    _ensure_camera()
    return StreamingResponse(
        camera_service.mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.post("/capture")
async def capture():
    """Capture a single frame and return it as a base64-encoded JPEG."""
    _ensure_camera()
    frame = camera_service.capture_frame()
    if frame is None:
        raise HTTPException(status_code=500, detail="Frame alınamadı.")
    jpeg = camera_service.frame_to_jpeg(frame)
    encoded = base64.b64encode(jpeg).decode()
    return {"image": encoded, "format": "jpeg"}


@router.post("/calibrate")
async def calibrate():
    """Run ArUco calibration on the current camera frame."""
    _ensure_camera()
    frame = camera_service.capture_frame()
    if frame is None:
        raise HTTPException(status_code=500, detail="Frame alınamadı.")
    result = run_calibration(frame)
    if not result["success"]:
        raise HTTPException(status_code=422, detail=result["error"])
    return result
