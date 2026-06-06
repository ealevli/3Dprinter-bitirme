"""
Printer serial service — sends G-code to Marlin line-by-line and waits for "ok".

Runs in a background thread so FastAPI endpoints are never blocked.

Ender 3 / Marlin 2.x specifics:
  - Baudrate: 115200
  - Boot: sends multiple "echo:" lines + "start" before accepting G-code
  - "ok" response may include temperature data: "ok T:20.0 /0.0 B:20.0 ..."
  - G28 (homing) takes 30-90s, G29 (bed leveling) can take 3+ min
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import serial
import serial.tools.list_ports

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

log = logging.getLogger(__name__)


class PrinterSerial:
    """Thread-safe Marlin G-code sender."""

    def __init__(self) -> None:
        self._ser: Optional[serial.Serial] = None
        # Separate locks: write lock guards _ser assignment + writes;
        # read lock guards reads so job thread can read while another
        # thread is NOT writing.
        self._write_lock = threading.Lock()
        self._read_lock  = threading.Lock()

        self._job_thread: Optional[threading.Thread] = None
        self._status       = "idle"
        self._current_line = 0
        self._total_lines  = 0
        self._stop_event   = threading.Event()
        self._start_time: Optional[float] = None
        self._last_error: str = ""
        self._stopped_by_user: bool = False

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self, port: str = None, baudrate: int = None) -> bool:
        """Open serial connection to Marlin and flush its boot messages."""
        if port     is None: port     = config.PRINTER_PORT
        if baudrate is None: baudrate = config.PRINTER_BAUDRATE

        log.info("[printer] connect() → port=%s  baudrate=%s", port, baudrate)

        with self._write_lock:
            if self._ser and self._ser.is_open:
                log.info("[printer] connect() → already connected")
                return True
            try:
                log.info("[printer] opening port %s …", port)
                self._ser = serial.Serial(port, baudrate, timeout=2, write_timeout=3)
                log.info("[printer] port opened — waiting 2 s for Marlin boot…")
                time.sleep(2)
                self._ser.reset_input_buffer()
                log.info("[printer] boot flush done — connection ready")
                self._last_error = ""
                return True
            except serial.SerialException as exc:
                log.error("[printer] connect() SerialException: %s", exc)
                self._last_error = str(exc)
                self._ser = None
                return False

    def disconnect(self) -> None:
        log.info("[printer] disconnect()")
        with self._write_lock:
            if self._ser and self._ser.is_open:
                self._ser.close()
            self._ser = None
        log.info("[printer] disconnected")

    @property
    def is_connected(self) -> bool:
        with self._write_lock:
            return self._ser is not None and self._ser.is_open

    # ── Low-level send ────────────────────────────────────────────────────────

    def send_line(self, line: str, timeout_s: float = 60.0) -> bool:
        """
        Send one G-code line, wait for Marlin's "ok" response.

        Marlin 2.x response types:
          "ok"                   — simple acknowledge → return True
          "ok T:20.0 /0.0 B:…"  — ack + temperatures → return True
          "echo:…"               — informational, keep waiting
          "busy: processing"     — Marlin busy, push deadline forward
          "wait"                 — Marlin idle, push deadline forward
          "Error:…" / "!!"       — fatal → return False
        """
        cmd = line.strip().split(";")[0].strip().upper()

        # Slow operations get a longer deadline
        if cmd.startswith("G28") or cmd.startswith("G29"):
            timeout_s = max(timeout_s, 180.0)

        log.debug("[printer] send_line(%r)  timeout=%.0fs", line.strip(), timeout_s)

        # ── Write ─────────────────────────────────────────────────────────────
        with self._write_lock:
            if not self._ser or not self._ser.is_open:
                self._last_error = "Yazıcı bağlı değil"
                log.warning("[printer] send_line: not connected")
                return False
            # Check BEFORE writing so no new command goes out after stop is requested.
            # This is the key race-condition fix: stop_event is set by emergency_stop()
            # before it tries to send M410, so if we check here we're guaranteed
            # the M410 (sent below in the read loop) is the LAST thing written.
            if self._stop_event.is_set():
                log.info("[printer] send_line: stop event already set — skipping write")
                return False
            try:
                self._ser.write((line.strip() + "\n").encode())
                log.debug("[printer] sent: %r — waiting for ok…", line.strip())
            except serial.SerialException as exc:
                log.error("[printer] write error: %s", exc)
                self._last_error = str(exc)
                return False

        # ── Read until "ok" ───────────────────────────────────────────────────
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self._stop_event.is_set():
                # Send M410 (quickstop) here — AFTER the write lock is released
                # and BEFORE any new command. This is the safe injection point.
                log.info("[printer] send_line: stop event — sending M410 quickstop")
                with self._write_lock:
                    if self._ser and self._ser.is_open:
                        try:
                            self._ser.write(b"M410\n")
                        except serial.SerialException:
                            pass
                return False
            try:
                with self._read_lock:
                    if not self._ser or not self._ser.is_open:
                        log.warning("[printer] send_line: connection lost during read")
                        return False
                    resp = self._ser.readline().decode(errors="replace").strip()
            except serial.SerialException as exc:
                log.error("[printer] read error: %s", exc)
                self._last_error = str(exc)
                return False

            if not resp:
                continue

            log.debug("[printer] rx: %r", resp)

            if resp.startswith("ok"):
                log.debug("[printer] send_line(%r) → ok", line.strip())
                return True
            if resp.upper().startswith("ERROR") or resp.startswith("!!"):
                self._last_error = resp
                log.error("[printer] Marlin error: %r", resp)
                return False
            # "busy: processing" or "wait" → reset deadline
            if resp.startswith("busy:") or resp == "wait":
                log.debug("[printer] Marlin busy/wait — pushing deadline")
                deadline = time.time() + timeout_s
                continue
            # echo:, temperatures, etc. → keep waiting

        self._last_error = f"Timeout ({timeout_s:.0f}s) — satır: {line.strip()[:60]}"
        log.warning("[printer] send_line TIMEOUT: %s", self._last_error)
        return False

    def emergency_stop(self) -> None:
        """
        Stop the current job and halt printer movement.

        Design: only set the stop event here.  M410 (quickstop) is injected by
        send_line() at the first safe point after its write lock is released.
        This prevents the race where M410 arrives BEFORE the last queued move,
        which would cause Marlin to stop — then immediately re-queue that move
        when send_line() writes it after M410.
        """
        log.info("[printer] emergency_stop() — setting stop event")
        self._stopped_by_user = True
        self._stop_event.set()
        # If no job thread is running (e.g. jog move), send M410 directly.
        if self._job_thread is None or not self._job_thread.is_alive():
            log.info("[printer] no active job thread — sending M410 directly")
            with self._write_lock:
                if self._ser and self._ser.is_open:
                    try:
                        self._ser.write(b"M410\n")
                    except serial.SerialException:
                        pass

    # ── BLTouch single-point probe ────────────────────────────────────────────

    def probe_z(self, x: float, y: float, timeout_s: float = 30.0) -> Optional[float]:
        """
        Send G30 single-point BLTouch probe and return the probed surface Z value.

        After G28, Marlin sets Z=0 at the nozzle position with M851 Z-offset applied.
        G30 at the part center probes the actual surface (including tape/part height)
        and reports:  "Bed X: 117.50 Y: 117.50 Z: 0.123"

        The returned Z is the nozzle coordinate at the surface.
        Moving to Z = probed_z + gap places the nozzle exactly `gap` mm above it.
        Returns None on failure or timeout.
        """
        cmd = f"G30 X{x:.3f} Y{y:.3f}"
        log.info("[printer] probe_z: %s", cmd)

        with self._write_lock:
            if not self._ser or not self._ser.is_open:
                self._last_error = "Yazici bagli degil"
                log.warning("[printer] probe_z: not connected")
                return None
            try:
                self._ser.write((cmd + "\n").encode())
            except serial.SerialException as exc:
                self._last_error = str(exc)
                log.error("[printer] probe_z write error: %s", exc)
                return None

        probed_z: Optional[float] = None
        deadline = time.time() + timeout_s

        while time.time() < deadline:
            try:
                with self._read_lock:
                    if not self._ser or not self._ser.is_open:
                        return None
                    resp = self._ser.readline().decode(errors="replace").strip()
            except serial.SerialException as exc:
                self._last_error = str(exc)
                return None

            if not resp:
                continue

            log.debug("[printer] probe_z rx: %r", resp)

            # Parse: "Bed X: 117.50 Y: 117.50 Z: 0.123"
            if "Bed" in resp and "Z:" in resp:
                try:
                    z_str = resp.split("Z:")[-1].strip().split()[0]
                    probed_z = float(z_str)
                    log.info("[printer] probe_z: surface Z = %.3f mm", probed_z)
                except (ValueError, IndexError):
                    log.warning("[printer] probe_z: could not parse Z from %r", resp)

            if resp.startswith("ok"):
                log.info("[printer] probe_z: done — Z = %s", probed_z)
                return probed_z

            if resp.upper().startswith("ERROR") or resp.startswith("!!"):
                self._last_error = resp
                log.error("[printer] probe_z Marlin error: %r", resp)
                return None

        self._last_error = f"G30 probe timeout ({timeout_s:.0f}s)"
        log.warning("[printer] probe_z: %s", self._last_error)
        return None

    # ── Job management ────────────────────────────────────────────────────────

    def send_gcode(self, gcode: str, job_id: str) -> None:
        """Start sending gcode in a background thread."""
        lines = [l for l in gcode.splitlines() if l.strip() and not l.strip().startswith(";")]
        self._total_lines   = len(lines)
        self._current_line  = 0
        self._last_error    = ""
        self._stopped_by_user = False
        self._stop_event.clear()
        self._status     = "running"
        self._start_time = time.time()

        log.info("[printer] send_gcode: job_id=%s  lines=%d", job_id, len(lines))

        self._job_thread = threading.Thread(
            target=self._send_worker, args=(lines,), daemon=True
        )
        self._job_thread.start()

    def _send_worker(self, lines: list[str]) -> None:
        try:
            for i, line in enumerate(lines):
                if self._stop_event.is_set():
                    self._status = "stopped"
                    log.info("[printer] job stopped by user at line %d/%d", i, len(lines))
                    return
                ok = self.send_line(line)
                self._current_line = i + 1
                if not ok:
                    self._status = "stopped" if self._stopped_by_user else "error"
                    log.error("[printer] job failed at line %d: %s", i + 1, self._last_error)
                    return
            self._status = "done"
            log.info("[printer] job done — %d lines sent", len(lines))
        finally:
            self._job_thread = None   # allow emergency_stop() to detect no active job

    def get_status(self) -> dict:
        elapsed = round(time.time() - self._start_time, 1) if self._start_time else 0
        return {
            "status":       self._status,
            "current_line": self._current_line,
            "total_lines":  self._total_lines,
            "elapsed_time": elapsed,
            "last_error":   self._last_error,
        }


printer_serial = PrinterSerial()
