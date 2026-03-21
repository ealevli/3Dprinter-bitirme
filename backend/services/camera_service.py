"""
Camera service — opens the USB camera, captures frames, and serves MJPEG stream.

Frame capture runs in a dedicated background thread so it never blocks the
FastAPI async event loop. The MJPEG generator is an async generator that reads
the latest frame from a shared buffer.
"""

import asyncio
import platform
import threading
import time
from typing import AsyncGenerator, Optional

import cv2
import numpy as np

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

# Use AVFoundation on macOS for better camera compatibility.
_BACKEND = cv2.CAP_AVFOUNDATION if platform.system() == "Darwin" else cv2.CAP_ANY


class CameraService:
    """Thread-safe wrapper around an OpenCV VideoCapture.

    A background thread continuously reads frames into ``_latest_frame``.
    The lock only protects lifecycle state (open/close), NOT frame reads,
    so a slow camera never blocks the main thread.
    """

    def __init__(self) -> None:
        self._cap: Optional[cv2.VideoCapture] = None
        self._lifecycle_lock = threading.Lock()   # guards _cap open/close
        self._frame_lock = threading.Lock()        # guards _latest_frame only
        self._latest_frame: Optional[np.ndarray] = None
        self._capture_thread: Optional[threading.Thread] = None
        self._running = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def open(self, index: int | None = None) -> bool:
        """Open the camera at *index* (defaults to config.CAMERA_INDEX)."""
        if index is None:
            index = config.CAMERA_INDEX
        with self._lifecycle_lock:
            if self._cap and self._cap.isOpened():
                return True
            cap = cv2.VideoCapture(index, _BACKEND)
            if not cap.isOpened():
                return False
            # Reduce internal buffer to 1 frame so we always get the latest image.
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            # Discard warm-up frames (macOS AVFoundation starts with black frames).
            for _ in range(10):
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
        with self._lifecycle_lock:
            self._running = False
            cap = self._cap
            self._cap = None
        # Release outside lifecycle lock to avoid deadlock with capture thread.
        if cap:
            cap.release()
        with self._frame_lock:
            self._latest_frame = None

    @property
    def is_open(self) -> bool:
        with self._lifecycle_lock:
            return self._cap is not None and self._cap.isOpened()

    # ── Background capture thread ──────────────────────────────────────────────

    def _capture_loop(self) -> None:
        """Continuously read frames from the camera into _latest_frame.

        Frame reads happen OUTSIDE the lifecycle lock so a slow/frozen camera
        never blocks other threads trying to open/close the camera.
        """
        while True:
            # Check running flag (under lifecycle lock) — grab cap reference.
            with self._lifecycle_lock:
                if not self._running or self._cap is None:
                    break
                cap = self._cap  # local ref; safe to use outside lock

            ret, frame = cap.read()   # blocking — but NOT holding any lock

            if not ret:
                # Camera stopped returning frames; wait briefly and retry.
                time.sleep(0.05)
                continue

            with self._frame_lock:
                self._latest_frame = frame

            time.sleep(1 / 30)  # ~30 fps cap

    # ── Frame access ──────────────────────────────────────────────────────────

    def capture_frame(self) -> Optional[np.ndarray]:
        """Return the most recent captured frame, or None if unavailable."""
        with self._frame_lock:
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

        Uses asyncio.sleep so it never blocks the FastAPI event loop.
        """
        if not self.is_open:
            self.open()

        # Give the capture thread time to fill the first frame.
        await asyncio.sleep(0.2)

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
