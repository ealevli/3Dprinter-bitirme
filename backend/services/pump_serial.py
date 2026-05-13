"""
Pump serial service — communicates with the Arduino pump controller.

Protocol (newline-terminated):
  Commands: START, STOP, SPEED:XXX, STATUS
  Replies:  OK, ERROR:message, STATUS:running:150
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import serial

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


class PumpSerial:
    """Thread-safe Arduino pump controller interface."""

    def __init__(self) -> None:
        self._ser: Optional[serial.Serial] = None
        self._lock = threading.Lock()
        self._running = False
        self._rpm = 0
        self._direction = "fwd"   # "fwd" | "rev"

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self, port: str = None, baudrate: int = None) -> bool:
        """Open serial connection to the Arduino. Returns True on success."""
        # Read config at call-time so runtime updates via /system/config are picked up
        if port is None:
            port = config.PUMP_PORT
        if baudrate is None:
            baudrate = config.PUMP_BAUDRATE
        with self._lock:
            if self._ser and self._ser.is_open:
                return True
            try:
                self._ser = serial.Serial(port, baudrate, timeout=5)
                time.sleep(1.5)         # Arduino resets on serial open
                return True
            except serial.SerialException as e:
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

    # ── Commands ──────────────────────────────────────────────────────────────

    def _send(self, cmd: str) -> str:
        """Send *cmd* and return the response line (caller must hold no lock)."""
        with self._lock:
            if not self._ser or not self._ser.is_open:
                return "ERROR:not connected"
            self._ser.write((cmd.strip() + "\n").encode())
            resp = self._ser.readline().decode(errors="replace").strip()
            return resp

    def start(self, rpm: int) -> bool:
        resp = self._send(f"SPEED:{rpm}")
        if "OK" not in resp and "ERROR" not in resp:
            pass  # old firmware may not respond to SPEED before START
        resp = self._send("START")
        if "OK" in resp:
            self._running = True
            self._rpm = rpm
            return True
        return False

    def stop(self) -> bool:
        resp = self._send("STOP")
        if "OK" in resp:
            self._running = False
            self._rpm = 0
            return True
        return False

    def set_speed(self, rpm: int) -> bool:
        resp = self._send(f"SPEED:{rpm}")
        if "OK" in resp:
            self._rpm = rpm
            return True
        return False

    def set_direction(self, forward: bool) -> bool:
        """Set motor direction. True = forward (coat), False = reverse (retract)."""
        resp = self._send(f"DIR:{1 if forward else 0}")
        if "OK" in resp:
            self._direction = "fwd" if forward else "rev"
            return True
        return False

    def prime(self, steps: int) -> bool:
        """Run the pump for a fixed number of steps (priming/purge)."""
        resp = self._send(f"PRIME:{steps}")
        if "OK" in resp:
            self._running = True
            return True
        return False

    def get_status(self) -> dict:
        """Query Arduino for live status."""
        resp = self._send("STATUS")
        # Format: STATUS:running:150:fwd  or  STATUS:stopped:0:rev
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

        return {"running": self._running, "rpm": self._rpm, "direction": self._direction}


pump_serial = PumpSerial()
