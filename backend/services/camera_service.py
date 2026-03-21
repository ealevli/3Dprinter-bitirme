"""
Camera service — opens the USB camera, captures frames, and serves MJPEG stream.

Frame capture runs in a dedicated background thread so it never blocks the
FastAPI async event loop. The MJPEG generator is an async generator that reads
the latest frame from a shared buffer.
"""

import asyncio
import threading
import time
from typing import AsyncGenerator, Optional

import cv2
import numpy as np

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


class CameraService:
    """Thread-safe wrapper around an OpenCV VideoCapture.

    A background thread continuously reads frames into ``_latest_frame``.
    All public methods are safe to call from any thread or async context.
    """

    def __init__(self) -> None:
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._capture_thread: Optional[threading.Thread] = None
        self._running = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def open(self, index: int | None = None) -> bool:
        """Open the camera at *index* (defaults to config.CAMERA_INDEX)."""
        if index is None:
            index = config.CAMERA_INDEX
        with self._lock:
            # Already open on the same index → nothing to do.
            if self._cap and self._cap.isOpened():
                return True
            cap = cv2.VideoCapture(index)
            if not cap.isOpened():
                return False
            # Discard warm-up frames (macOS AVFoundation produces black frames initially).
            for _ in range(5):
                cap.read()
            self._cap = cap
            self._running = True

        # Start background capture thread.
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="camera-capture"
        )
        self._capture_thread.start()
        return True

    def close(self) -> None:
        """Release the camera and stop the background thread."""
        with self._lock:
            self._running = False
            if self._cap:
                self._cap.release()
                self._cap = None
            self._latest_frame = None

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._cap is not None and self._cap.isOpened()

    # ── Background capture thread ──────────────────────────────────────────────

    def _capture_loop(self) -> None:
        """Continuously read frames from the camera into _latest_frame."""
        while True:
            with self._lock:
                if not self._running or self._cap is None:
                    break
                ret, frame = self._cap.read()
                if ret:
                    self._latest_frame = frame
            # ~30 fps — sleep outside the lock so other threads can access _cap.
            time.sleep(1 / 30)

    # ── Frame access ──────────────────────────────────────────────────────────

    def capture_frame(self) -> Optional[np.ndarray]:
        """Return the most recent captured frame, or None if unavailable."""
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def frame_to_jpeg(self, frame: np.ndarray) -> bytes:
        """Encode an OpenCV BGR frame to JPEG bytes."""
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buffer.tobytes()

    # ── MJPEG async stream ────────────────────────────────────────────────────

    async def mjpeg_generator(self) -> AsyncGenerator[bytes, None]:
        """Async generator that yields multipart JPEG frames.

        Using an *async* generator with ``asyncio.sleep`` ensures we never
        block the FastAPI event loop.
        """
        if not self.is_open:
            self.open()

        # Give the capture thread a moment to fill the first frame.
        await asyncio.sleep(0.1)

        while self.is_open:
            frame = self.capture_frame()
            if frame is None:
                await asyncio.sleep(0.05)
                continue

            jpeg = self.frame_to_jpeg(frame)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            )
            await asyncio.sleep(1 / 25)  # ~25 fps


# Module-level singleton — import and use directly.
camera_service = CameraService()
