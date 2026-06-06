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

if platform.system() == "Darwin":
    _BACKEND = cv2.CAP_AVFOUNDATION
elif platform.system() == "Windows":
    # CAP_MSMF (Windows Media Foundation) is more reliable than CAP_DSHOW
    # on Windows 10/11 — DirectShow fails with "can't be used to capture by index"
    # on many USB cameras.
    _BACKEND = cv2.CAP_MSMF
else:
    _BACKEND = cv2.CAP_ANY


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
        self._encode_lock = threading.Lock()       # guards cv2.imencode (not thread-safe on Windows)
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_time: float = 0.0              # timestamp of latest stored frame
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
                # CAP_MSMF failed — fall back to CAP_ANY
                cap = cv2.VideoCapture(index, cv2.CAP_ANY)
                if not cap.isOpened():
                    return False
            # Reduce internal buffer to 1 frame so we always get the latest image.
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            # Discard warm-up frames — USB cameras often return black frames at start.
            for _ in range(30):
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
        """Continuously read frames from the camera into _latest_frame."""
        while True:
            with self._lifecycle_lock:
                if not self._running or self._cap is None:
                    break
                cap = self._cap

            try:
                ret, frame = cap.read()
            except Exception:
                time.sleep(0.1)
                continue

            if not ret or frame is None:
                time.sleep(0.05)
                continue

            frame_copy = frame.copy()
            with self._frame_lock:
                self._latest_frame = frame_copy
                self._frame_time = time.time()

            # Throttle to ~20 fps max — prevents MSMF buffer overflow on Windows
            # which causes segfaults when detection also reads from the camera.
            time.sleep(0.05)

    # ── Frame access ──────────────────────────────────────────────────────────

    def capture_frame(self) -> Optional[np.ndarray]:
        """Return the most recent captured frame, or None if unavailable."""
        with self._frame_lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def capture_fresh_frame(self, timeout: float = 3.0) -> Optional[np.ndarray]:
        """Wait for a frame captured AFTER this call was made, then return it.

        Prevents calibration from reusing a stale/frozen frame.
        """
        deadline = time.time() + timeout
        t_start = time.time()
        while time.time() < deadline:
            with self._frame_lock:
                if self._frame_time > t_start and self._latest_frame is not None:
                    return self._latest_frame.copy()
            time.sleep(0.05)
        return None

    def frame_to_jpeg(self, frame: np.ndarray) -> bytes:
        """Encode an OpenCV BGR frame to JPEG bytes (thread-safe)."""
        with self._encode_lock:
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return buffer.tobytes()

    # ── Bed overlay ───────────────────────────────────────────────────────────

    def _draw_bed_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Draw 235x235 mm bed boundary + center crosshair on the frame.

        Uses the saved homography (mm to pixel via H-inv) so the overlay
        aligns with the physical printer bed even if the camera is tilted.
        Returns the original frame unchanged if calibration is not available.
        """
        try:
            from services.calibration import load_calibration, mm_to_pixel
        except ImportError:
            return frame

        H = load_calibration()
        if H is None:
            return frame

        out = frame.copy()
        BED_W, BED_H = 235.0, 235.0

        # Bed boundary
        corners_mm = [(0.0, 0.0), (BED_W, 0.0), (BED_W, BED_H), (0.0, BED_H)]
        try:
            corners_px = [mm_to_pixel(x, y, H) for x, y in corners_mm]
        except Exception:
            return frame

        pts = np.array([(int(x), int(y)) for x, y in corners_px], dtype=np.int32)
        cv2.polylines(out, [pts.reshape(-1, 1, 2)], True, (0, 220, 220), 2)

        # Center crosshair at (117.5, 117.5) mm — BLTouch probe point
        try:
            cx_px, cy_px = mm_to_pixel(BED_W / 2, BED_H / 2, H)
        except Exception:
            return out
        cx_px, cy_px = int(cx_px), int(cy_px)

        arm = 35
        cv2.line(out, (cx_px - arm, cy_px), (cx_px + arm, cy_px), (0, 80, 255), 2)
        cv2.line(out, (cx_px, cy_px - arm), (cx_px, cy_px + arm), (0, 80, 255), 2)
        cv2.circle(out, (cx_px, cy_px), 5, (0, 80, 255), -1)
        cv2.putText(out, "Merkez / BLTouch", (cx_px + 8, cy_px - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 80, 255), 1, cv2.LINE_AA)

        return out

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

            frame = self._draw_bed_overlay(frame)

            jpeg = self.frame_to_jpeg(frame)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            )
            await asyncio.sleep(1 / 25)  # ~25 fps


# Module-level singleton — import and use directly.
camera_service = CameraService()
