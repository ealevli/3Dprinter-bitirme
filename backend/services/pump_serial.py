"""
Pump serial service — communicates with the Arduino pump controller.

Protocol (newline-terminated):
  Commands: START, STOP, SPEED:XXX, STATUS, DIR:0/1, PRIME:N
  Replies:  OK, ERROR:message, STATUS:running:150:fwd

Freeze-safety design
--------------------
• ser.timeout = 1.0   → each readline() returns in at most 1 s
• _send deadline = 3.0 → at most 3 readline attempts per command (3 s worst case)
• write_timeout = 2.0 → write() never hangs either
• asyncio.wait_for wrappers in the router give a hard HTTP-level timeout on top
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import serial

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

log = logging.getLogger(__name__)

# How long a single readline() call may block (seconds)
_READLINE_TIMEOUT = 1.0
# Total deadline for one _send() attempt (seconds)
_SEND_DEADLINE = 3.0


class PumpSerial:
    """Thread-safe Arduino pump controller interface."""

    def __init__(self) -> None:
        self._ser: Optional[serial.Serial] = None
        self._lock = threading.Lock()
        self._running = False
        self._rpm = 0
        self._direction = "fwd"   # "fwd" | "rev"
        self._connecting = False
        self._last_error: str = ""

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self, port: str = None, baudrate: int = None) -> bool:
        """Open serial connection to the Arduino. Returns True on success."""
        if port is None:
            port = config.PUMP_PORT
        if baudrate is None:
            baudrate = config.PUMP_BAUDRATE

        log.info("[pump] connect() → port=%s  baudrate=%s", port, baudrate)

        with self._lock:
            if self._ser and self._ser.is_open:
                log.info("[pump] connect() → already open, skipping")
                return True
            if self._connecting:
                log.warning("[pump] connect() → already in progress, skipping")
                return False
            self._connecting = True

        # Open OUTSIDE the lock so is_connected / status queries don't stall
        try:
            log.info("[pump] opening port %s …", port)
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = baudrate
            ser.timeout = _READLINE_TIMEOUT   # 1 s per readline
            ser.write_timeout = 2.0           # prevent write() from hanging too
            ser.open()
            log.info("[pump] port opened — waiting 1.5 s for Arduino boot…")
            time.sleep(1.5)
            log.info("[pump] boot wait done — probing Arduino with STATUS…")

            # ── Probe: verify this port is actually an Arduino ────────────────
            # A Bluetooth ghost port (or any wrong port) opens successfully on
            # Windows but either raises WriteTimeout or never sends a response.
            # We catch both here so connect() returns False instead of True for
            # phantom ports.
            ser.reset_input_buffer()
            try:
                ser.write(b"STATUS\n")
            except serial.SerialTimeoutException:
                ser.close()
                self._last_error = (
                    "Write timeout — port açıldı ama Arduino cevap veremiyor. "
                    "Bluetooth veya hayalet port seçmiş olabilirsiniz. "
                    "Aygıt Yöneticisi'nde Arduino'nun gerçek USB portunu bulun (CH340/CP210x)."
                )
                log.error("[pump] connect() probe write timeout on %s — %s", port, self._last_error)
                with self._lock:
                    self._connecting = False
                return False

            # Wait up to 3 s for STATUS:... READY, or OK
            deadline = time.time() + 3.0
            verified = False
            while time.time() < deadline:
                line = ser.readline().decode(errors="replace").strip()
                if not line:
                    continue
                log.debug("[pump] connect() probe rx: %r", line)
                if line.startswith(("STATUS:", "READY", "OK")):
                    verified = True
                    break

            if not verified:
                ser.close()
                self._last_error = (
                    f"Arduino cevap vermedi (port: {port}, baud: {baudrate}). "
                    "Baud rate yanlış veya bu port Arduino değil. "
                    "Firmware yüklü mü? Başka uygulama portu açık mı?"
                )
                log.error("[pump] connect() probe: no valid response — %s", self._last_error)
                with self._lock:
                    self._connecting = False
                return False

            log.info("[pump] probe OK — Arduino confirmed on %s", port)
            with self._lock:
                self._ser = ser
                self._connecting = False
                self._last_error = ""
            return True

        except serial.SerialException as exc:
            log.error("[pump] connect() SerialException: %s", exc)
            self._last_error = str(exc)
            with self._lock:
                self._connecting = False
            return False

        except Exception as exc:
            log.error("[pump] connect() unexpected error: %s", exc)
            self._last_error = str(exc)
            with self._lock:
                self._connecting = False
            return False

    def disconnect(self) -> None:
        log.info("[pump] disconnect()")
        with self._lock:
            if self._ser and self._ser.is_open:
                self._ser.close()
            self._ser = None
        log.info("[pump] disconnected")

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._ser is not None and self._ser.is_open

    @property
    def last_error(self) -> str:
        return self._last_error

    # ── Internal send/receive ─────────────────────────────────────────────────

    def _send(self, cmd: str) -> str:
        """
        Send *cmd* and return the first OK / ERROR / STATUS response line.

        Worst-case duration: _SEND_DEADLINE seconds (≈ 3 s).
        The lock is held for the entire write+read cycle to prevent interleaving.
        """
        log.debug("[pump] _send(%r) — acquiring lock", cmd)
        with self._lock:
            if not self._ser or not self._ser.is_open:
                log.warning("[pump] _send(%r) → not connected", cmd)
                return "ERROR:not connected"

            try:
                self._ser.reset_input_buffer()
                self._ser.write((cmd.strip() + "\n").encode())
                log.debug("[pump] _send(%r) written — waiting for response…", cmd)

                deadline = time.time() + _SEND_DEADLINE
                attempt = 0
                while time.time() < deadline:
                    attempt += 1
                    # readline() returns after _READLINE_TIMEOUT seconds at most
                    line = self._ser.readline().decode(errors="replace").strip()
                    if not line:
                        log.debug("[pump] _send(%r) attempt %d — empty (no data yet)", cmd, attempt)
                        continue
                    log.debug("[pump] _send(%r) attempt %d — raw=%r", cmd, attempt, line)
                    if line.startswith(("OK", "ERROR", "STATUS")):
                        log.info("[pump] _send(%r) → %r", cmd, line)
                        return line
                    # Arduino can print extra debug lines; skip them
                    log.debug("[pump] _send(%r) skipping non-response line: %r", cmd, line)

                log.warning("[pump] _send(%r) → TIMEOUT after %.1f s (%d attempts)", cmd, _SEND_DEADLINE, attempt)
                self._last_error = f"timeout waiting for response to {cmd!r}"
                return "ERROR:timeout"

            except serial.SerialException as exc:
                log.error("[pump] _send(%r) SerialException: %s", cmd, exc)
                # Explicitly close before clearing — otherwise the OS port handle
                # stays open and blocks Arduino IDE / other tools from accessing it.
                try:
                    self._ser.close()
                except Exception:
                    pass
                self._ser = None
                self._last_error = str(exc)
                return "ERROR:disconnected"

            except Exception as exc:
                log.error("[pump] _send(%r) unexpected error: %s", cmd, exc)
                self._last_error = str(exc)
                return "ERROR:exception"

    # ── Public commands ───────────────────────────────────────────────────────

    def start(self, rpm: int) -> bool:
        log.info("[pump] start(rpm=%d)", rpm)
        self._send(f"SPEED:{rpm}")
        resp = self._send("START")
        log.info("[pump] start → %r", resp)
        if "OK" in resp:
            self._running = True
            self._rpm = rpm
            return True
        self._last_error = resp
        return False

    def stop(self) -> bool:
        log.info("[pump] stop()")
        resp = self._send("STOP")
        log.info("[pump] stop → %r", resp)
        if "OK" in resp:
            self._running = False
            self._rpm = 0
            return True
        self._last_error = resp
        return False

    def set_speed(self, rpm: int) -> bool:
        log.info("[pump] set_speed(rpm=%d)", rpm)
        resp = self._send(f"SPEED:{rpm}")
        log.info("[pump] set_speed → %r", resp)
        if "OK" in resp:
            self._rpm = rpm
            return True
        self._last_error = resp
        return False

    def set_direction(self, forward: bool) -> bool:
        log.info("[pump] set_direction(forward=%s)", forward)
        resp = self._send(f"DIR:{1 if forward else 0}")
        log.info("[pump] set_direction → %r", resp)
        if "OK" in resp:
            self._direction = "fwd" if forward else "rev"
            return True
        self._last_error = resp
        return False

    def prime(self, steps: int) -> bool:
        log.info("[pump] prime(steps=%d)", steps)
        resp = self._send(f"PRIME:{steps}")
        log.info("[pump] prime → %r", resp)
        if "OK" in resp:
            self._running = True
            return True
        self._last_error = resp
        return False

    def get_status(self) -> dict:
        """Query Arduino for live status. Falls back to cached state on timeout."""
        log.debug("[pump] get_status()")
        resp = self._send("STATUS")
        log.debug("[pump] get_status → %r", resp)

        if resp.startswith("STATUS:"):
            parts = resp.split(":")
            if len(parts) >= 3:
                self._running = parts[1] == "running"
                try:
                    self._rpm = int(parts[2])
                except ValueError:
                    pass
            if len(parts) >= 4:
                self._direction = parts[3]
        # On timeout/error return cached state so UI doesn't reset to defaults
        return {
            "running": self._running,
            "rpm": self._rpm,
            "direction": self._direction,
            "last_error": self._last_error if not resp.startswith("STATUS:") else "",
        }


pump_serial = PumpSerial()
