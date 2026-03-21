"""
Camera service — opens the USB camera, captures frames, and serves MJPEG stream.
"""

import io
import time
import threading
from typing import Generator, Optional

import cv2
import numpy as np

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


class CameraService:
    """Thread-safe wrapper around an OpenCV VideoCapture."""

    def __init__(self) -> None:
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._running = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def open(self, index: int = config.CAMERA_INDEX) -> bool:
        """Open the camera at *index*. Returns True on success."""
        with self._lock:
            if self._cap and self._cap.isOpened():
                return True
            self._cap = cv2.VideoCapture(index)
            if not self._cap.isOpened():
                self._cap = None
                return False
            # Discard the first few frames — many cameras produce black frames
            # while warming up (especially on macOS with AVFoundation).
            for _ in range(5):
                self._cap.read()
            self._running = True
            return True

    def close(self) -> None:
        """Release the camera."""
        with self._lock:
            self._running = False
            if self._cap:
                self._cap.release()
                self._cap = None

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._cap is not None and self._cap.isOpened()

    # ── Frame Capture ─────────────────────────────────────────────────────────

    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture and return a single BGR frame, or None on failure."""
        with self._lock:
            if not self._cap or not self._cap.isOpened():
                return None
            ret, frame = self._cap.read()
            if not ret:
                return None
            self._latest_frame = frame
            return frame.copy()

    def frame_to_jpeg(self, frame: np.ndarray) -> bytes:
        """Encode an OpenCV BGR frame to JPEG bytes."""
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buffer.tobytes()

    # ── MJPEG Stream ──────────────────────────────────────────────────────────

    def mjpeg_generator(self) -> Generator[bytes, None, None]:
        """
        Yields multipart JPEG frames for a streaming HTTP response.
        Usage: StreamingResponse(camera.mjpeg_generator(), media_type="multipart/x-mixed-replace; boundary=frame")
        """
        if not self.is_open:
            self.open()

        while True:
            frame = self.capture_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            jpeg = self.frame_to_jpeg(frame)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            )
            time.sleep(1 / 30)  # ~30 fps cap


# Module-level singleton — import and use directly.
camera_service = CameraService()
