"""
Printer serial service — sends G-code to Marlin line-by-line and waits for "ok".

Runs in a background thread so FastAPI endpoints are never blocked.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import serial
import serial.tools.list_ports

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


class PrinterSerial:
    """Thread-safe Marlin G-code sender."""

    def __init__(self) -> None:
        self._ser: Optional[serial.Serial] = None
        self._lock = threading.Lock()

        # Job tracking.
        self._job_thread: Optional[threading.Thread] = None
        self._status = "idle"          # idle | running | paused | done | error
        self._current_line = 0
        self._total_lines = 0
        self._stop_event = threading.Event()
        self._start_time: Optional[float] = None

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self, port: str = config.PRINTER_PORT, baudrate: int = config.PRINTER_BAUDRATE) -> bool:
        """Open the serial connection to Marlin. Returns True on success."""
        with self._lock:
            if self._ser and self._ser.is_open:
                return True
            try:
                self._ser = serial.Serial(port, baudrate, timeout=30)
                time.sleep(2)           # wait for Marlin boot
                self._ser.readline()    # discard boot message
                return True
            except serial.SerialException as exc:
                self._ser = None
                return False

    def disconnect(self) -> None:
        with self._lock:
            if self._ser and self._ser.is_open:
                self._ser.close()
            self._ser = None

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._ser is not None and self._ser.is_open

    # ── Low-level send ────────────────────────────────────────────────────────

    def send_line(self, line: str, timeout_s: float = 30.0) -> bool:
        """
        Send a single G-code line and block until Marlin responds with "ok".
        Returns True on success.
        """
        with self._lock:
            if not self._ser or not self._ser.is_open:
                return False
            self._ser.write((line.strip() + "\n").encode())
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                resp = self._ser.readline().decode(errors="replace").strip()
                if resp == "ok":
                    return True
                if resp.startswith("Error"):
                    return False
            return False  # timeout

    def emergency_stop(self) -> None:
        """Send M112 and stop the current job immediately."""
        self._stop_event.set()
        with self._lock:
            if self._ser and self._ser.is_open:
                self._ser.write(b"M112\n")

    # ── Job management ────────────────────────────────────────────────────────

    def send_gcode(self, gcode: str, job_id: str) -> None:
        """Start sending *gcode* in a background thread."""
        lines = [l for l in gcode.splitlines() if l.strip()]
        self._total_lines = len(lines)
        self._current_line = 0
        self._stop_event.clear()
        self._status = "running"
        self._start_time = time.time()

        self._job_thread = threading.Thread(
            target=self._send_worker, args=(lines,), daemon=True
        )
        self._job_thread.start()

    def _send_worker(self, lines: list[str]) -> None:
        for i, line in enumerate(lines):
            if self._stop_event.is_set():
                self._status = "idle"
                return
            ok = self.send_line(line)
            self._current_line = i + 1
            if not ok:
                self._status = "error"
                return
        self._status = "done"

    def get_status(self) -> dict:
        elapsed = round(time.time() - self._start_time, 1) if self._start_time else 0
        return {
            "status": self._status,
            "current_line": self._current_line,
            "total_lines": self._total_lines,
            "elapsed_time": elapsed,
        }


printer_serial = PrinterSerial()
