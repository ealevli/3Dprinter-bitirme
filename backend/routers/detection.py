"""
Detection router.

Endpoints:
  POST /detect           → detect part in current camera frame
  POST /detect/preview   → detect + return annotated image (base64)
"""

import base64
from fastapi import APIRouter, HTTPException

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from services.camera_service import camera_service
from services.detection import detect_part, annotate_frame

router = APIRouter()


def _get_frame():
    if not camera_service.is_open:
        camera_service.open()
    frame = camera_service.capture_frame()
    if frame is None:
        raise HTTPException(status_code=503, detail="Kamera frame alınamadı.")
    return frame


@router.post("")
async def detect():
    """Detect the part in the current camera frame."""
    frame = _get_frame()
    result = detect_part(frame)
    return result


@router.post("/preview")
async def detect_preview():
    """Detect the part and return an annotated JPEG image (base64)."""
    frame = _get_frame()
    result = detect_part(frame)
    annotated = annotate_frame(frame, result)
    jpeg = camera_service.frame_to_jpeg(annotated)
    encoded = base64.b64encode(jpeg).decode()
    return {**result, "image": encoded}
