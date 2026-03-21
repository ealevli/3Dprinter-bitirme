"""
Camera router.

Endpoints:
  GET  /camera/stream     → MJPEG video stream
  POST /camera/capture    → single JPEG frame (base64)
  POST /camera/calibrate  → ArUco calibration
"""

import base64
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

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


@router.get("/frame")
async def frame():
    """Return the latest camera frame as a raw JPEG (no base64).
    Frontend polls this endpoint every ~100ms instead of using MJPEG stream.
    Much more robust — each request is independent, no persistent connection to freeze.
    """
    _ensure_camera()
    img = camera_service.capture_frame()
    if img is None:
        raise HTTPException(status_code=503, detail="Frame yok.")
    jpeg = camera_service.frame_to_jpeg(img)
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
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


@router.get("/scan")
async def scan_cameras():
    """
    Scan camera indices 0-7 and return which ones are accessible.
    Runs in a thread executor to avoid blocking the event loop.
    """
    import asyncio
    import cv2 as _cv2

    def _scan():
        found = []
        for i in range(8):
            cap = _cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                found.append({"index": i, "readable": ret})
                cap.release()
        return found

    loop = asyncio.get_event_loop()
    cameras = await loop.run_in_executor(None, _scan)
    return {"cameras": cameras}


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
