"""
Detection router.

Endpoints:
  POST /detect           → detect part in current camera frame
  POST /detect/preview   → detect + return annotated image (base64)

Concurrency: only one detection runs at a time (semaphore).
Heavy CV work is offloaded to a thread pool so the event loop stays free.
"""

import asyncio
import base64
from fastapi import APIRouter, HTTPException

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from services.camera_service import camera_service
from services.detection import detect_part, annotate_frame

router = APIRouter()

# Only 1 detection at a time — prevents CPU pileup on rapid button presses.
_detection_sem = asyncio.Semaphore(1)


def _get_frame():
    if not camera_service.is_open:
        camera_service.open()
    frame = camera_service.capture_frame()
    if frame is None:
        raise HTTPException(status_code=503, detail="Kamera frame alınamadı.")
    return frame


def _run_detection(frame):
    """Sync wrapper — runs in thread pool via run_in_executor."""
    result = detect_part(frame)
    annotated = annotate_frame(frame, result)
    jpeg = camera_service.frame_to_jpeg(annotated)
    encoded = base64.b64encode(jpeg).decode()
    return result, encoded


@router.post("")
async def detect():
    """Detect the part in the current camera frame."""
    if _detection_sem.locked():
        raise HTTPException(status_code=429, detail="Tarama zaten çalışıyor, bekleyin.")
    async with _detection_sem:
        frame = _get_frame()
        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, detect_part, frame),
                timeout=15.0,
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Tespit zaman aşımı (15s).")
        return result


@router.post("/preview")
async def detect_preview():
    """Detect the part and return an annotated JPEG image (base64)."""
    if _detection_sem.locked():
        raise HTTPException(status_code=429, detail="Tarama zaten çalışıyor, bekleyin.")
    async with _detection_sem:
        frame = _get_frame()
        loop = asyncio.get_event_loop()
        try:
            result, encoded = await asyncio.wait_for(
                loop.run_in_executor(None, _run_detection, frame),
                timeout=15.0,
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Tespit zaman aşımı (15s).")
        return {**result, "image": encoded}
