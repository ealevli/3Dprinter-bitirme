"""
Printer serial service — sends G-code to Marlin line-by-line and waits for "ok".

Runs in a background thread so FastAPI endpoints are never blocked.

Ender 3 S1 Pro / Marlin 2.x specifics:
  - Baudrate: 115200
  - Boot: sends multiple "echo:" lines + "start" before accepting G-code
  - "ok" response may include temperature data: "ok T:20.0 /0.0 B:20.0 ..."
  - G28 (homing) takes 30-90s, G29 (bed leveling) can take 3+ min
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
        # Separate locks: one for writing, one for reading.
        # Using a single lock caused deadlocks during long G28/G29 timeouts.
        self._write_lock = threading.Lock()
        self._read_lock = threading.Lock()

        self._job_thread: Optional[threading.Thread] = None
        self._status = "idle"       # idle | running | done | error
        self._current_line = 0
        self._total_lines = 0
        self._stop_event = threading.Event()
        self._start_time: Optional[float] = None
        self._last_error: str = ""
        self._stopped_by_user: bool = False

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self, port: str = config.PRINTER_PORT, baudrate: int = config.PRINTER_BAUDRATE) -> bool:
        """Open serial connection to Marlin and flush its boot messages."""
        with self._write_lock:
            if self._ser and self._ser.is_open:
                return True
            try:
                self._ser = serial.Serial(port, baudrate, timeout=2)
                # Wait for Marlin to boot (sends "echo:..." and "start")
                time.sleep(2)
                # Flush all pending boot messages so they don't pollute responses
                self._ser.reset_input_buffer()
                return True
            except serial.SerialException:
                self._ser = None
                return False

    def disconnect(self) -> None:
        with self._write_lock:
            if self._ser and self._ser.is_open:
                self._ser.close()
            self._ser = None

    @property
    def is_connected(self) -> bool:
        with self._write_lock:
            return self._ser is not None and self._ser.is_open

    # ── Low-level send ────────────────────────────────────────────────────────

    def send_line(self, line: str, timeout_s: float = 30.0) -> bool:
        """
        Send one G-code line, wait for Marlin's "ok" response.

        Marlin 2.x may respond with:
          "ok"                    — simple acknowledge
          "ok T:20.0 /0.0 B:..."  — acknowledge + temperatures
          "echo:..."              — informational, keep waiting
          "Error:..."             — fatal, return False
          "!!"                    — emergency, return False
        """
        cmd = line.strip().split(";")[0].strip().upper()

        # G28 (home) and G29 (bed level) are slow operations
        if cmd.startswith("G28") or cmd.startswith("G29"):
            timeout_s = max(timeout_s, 120.0)

        with self._write_lock:
            if not self._ser or not self._ser.is_open:
                self._last_error = "Yazıcı bağlı değil"
                return False
            try:
                self._ser.write((line.strip() + "\n").encode())
            except serial.SerialException as e:
                self._last_error = str(e)
                return False

        # Read responses until "ok" without holding the write lock
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self._stop_event.is_set():
                return False
            try:
                with self._read_lock:
                    if not self._ser or not self._ser.is_open:
                        return False
                    resp = self._ser.readline().decode(errors="replace").strip()
            except serial.SerialException as e:
                self._last_error = str(e)
                return False

            if not resp:
                continue
            if resp.startswith("ok"):
                return True
            if resp.upper().startswith("ERROR") or resp.startswith("!!"):
                self._last_error = resp
                return False
            # echo:, busy:, etc. → keep waiting

        self._last_error = f"Timeout ({timeout_s:.0f}s) — satır: {line.strip()[:60]}"
        return False

    def emergency_stop(self) -> None:
        """Stop the current job and halt printer movement."""
        self._stopped_by_user = True
        self._stop_event.set()
        with self._write_lock:
            if self._ser and self._ser.is_open:
                try:
                    # M410 = quickstop (keeps motors on, recoverable)
                    # M112 = emergency stop (requires reset — too aggressive for coating)
                    self._ser.write(b"M410\n")
                except serial.SerialException:
                    pass

    # ── Job management ────────────────────────────────────────────────────────

    def send_gcode(self, gcode: str, job_id: str) -> None:
        """Start sending gcode in a background thread."""
        # Skip pure comment lines and blank lines
        lines = [l for l in gcode.splitlines() if l.strip() and not l.strip().startswith(";")]
        self._total_lines = len(lines)
        self._current_line = 0
        self._last_error = ""
        self._stopped_by_user = False
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
                self._status = "stopped"
                return
            ok = self.send_line(line)
            self._current_line = i + 1
            if not ok:
                self._status = "stopped" if self._stopped_by_user else "error"
                return
        self._status = "done"

    def get_status(self) -> dict:
        elapsed = round(time.time() - self._start_time, 1) if self._start_time else 0
        return {
            "status": self._status,
            "current_line": self._current_line,
            "total_lines": self._total_lines,
            "elapsed_time": elapsed,
            "last_error": self._last_error,
        }


printer_serial = PrinterSerial()
