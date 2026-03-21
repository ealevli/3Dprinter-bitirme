"""
Camera router.

Endpoints:
  GET  /camera/stream     → MJPEG video stream
  GET  /camera/frame      → single JPEG (polled by frontend)
  POST /camera/capture    → single JPEG frame (base64)
  GET  /camera/scan       → find available camera indices
  POST /camera/calibrate  → ArUco calibration
"""

import asyncio
import base64
import os
import sys

import cv2
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from services.camera_service import camera_service, _BACKEND
from services.calibration import run_calibration

router = APIRouter()

# Scan and calibrate share this semaphore — only one heavy camera op at a time.
_cam_op_sem = asyncio.Semaphore(1)


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
    """MJPEG stream."""
    _ensure_camera()
    return StreamingResponse(
        camera_service.mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/frame")
async def frame():
    """Return the latest camera frame as a raw JPEG (polled by frontend)."""
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
    img = camera_service.capture_frame()
    if img is None:
        raise HTTPException(status_code=500, detail="Frame alınamadı.")
    jpeg = camera_service.frame_to_jpeg(img)
    encoded = base64.b64encode(jpeg).decode()
    return {"image": encoded, "format": "jpeg"}


@router.get("/scan")
async def scan_cameras():
    """
    Scan camera indices 0–7 and report which are available.

    Key safety rules:
    - The currently open camera index is reported as available WITHOUT
      reopening it (avoids crashing the live feed on macOS AVFoundation).
    - Other indices are tested one at a time in a thread executor.
    - Indices beyond the OS limit are skipped immediately (no trial open).
    """
    if _cam_op_sem.locked():
        raise HTTPException(status_code=429, detail="Başka bir kamera işlemi çalışıyor.")

    active_index = config.CAMERA_INDEX  # currently configured index

    def _probe(idx: int) -> dict:
        """Try to open one camera index and read a frame. Must be brief."""
        # Don't touch the already-open camera — report it based on service state.
        if idx == active_index and camera_service.is_open:
            frame = camera_service.capture_frame()
            return {"index": idx, "readable": frame is not None, "active": True}

        # Temporarily open with explicit backend to avoid triggering FFMPEG warnings.
        cap = cv2.VideoCapture(idx, _BACKEND)
        if not cap.isOpened():
            cap.release()
            return {"index": idx, "readable": False, "active": False}
        ret, _ = cap.read()
        cap.release()
        return {"index": idx, "readable": ret, "active": False}

    async with _cam_op_sem:
        loop = asyncio.get_event_loop()
        results = []
        for i in range(8):
            info = await loop.run_in_executor(None, _probe, i)
            # Stop scanning once we hit two consecutive unopenable indices
            # (avoids triggering AVFoundation errors for non-existent devices)
            if not info["readable"] and not info["active"]:
                # Check one more before giving up
                if i > 0 and not results[-1]["readable"] and not results[-1].get("active"):
                    break
            results.append(info)

        return {"cameras": [r for r in results if r["readable"] or r["active"]]}


@router.post("/calibrate")
async def calibrate():
    """Run ArUco calibration on the current camera frame."""
    if _cam_op_sem.locked():
        raise HTTPException(status_code=429, detail="Başka bir kamera işlemi çalışıyor.")

    _ensure_camera()

    async with _cam_op_sem:
        loop = asyncio.get_event_loop()

        def _best_frame_calibrate():
            """
            Take up to 5 frames and calibrate with the one where the most
            ArUco markers are visible. Avoids single-frame bad captures.
            """
            import time
            from services.calibration import detect_markers, compute_homography, save_calibration

            best_frame = None
            best_count = 0

            for _ in range(5):
                frame = camera_service.capture_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue
                markers = detect_markers(frame)
                if len(markers) > best_count:
                    best_count = len(markers)
                    best_frame = frame
                if best_count >= 4:
                    break
                time.sleep(0.15)  # wait for next frame from capture thread

            if best_frame is None:
                return {"success": False, "matrix": None,
                        "error": "Kamera frame alınamadı."}

            return run_calibration(best_frame)

        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, _best_frame_calibrate),
                timeout=20.0,
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Kalibrasyon zaman aşımı.")

    if not result["success"]:
        raise HTTPException(status_code=422, detail=result["error"])
    return result
