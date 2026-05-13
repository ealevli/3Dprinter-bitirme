"""
Configuration module for the 3D Printer Coating System.
All hardware-specific settings are centralized here — never hardcode these elsewhere.

User-modified settings are persisted to data/user_config.json so they survive
server restarts.  Call save_user_config() after any runtime update.
"""

import json
import os

# ── Serial Ports ──────────────────────────────────────────────────────────────
PRINTER_PORT = "/dev/ttyUSB0"       # Linux default; Windows: "COM4"
PRINTER_BAUDRATE = 115200

PUMP_PORT = "/dev/ttyACM0"          # Linux default; Windows: "COM3"
PUMP_BAUDRATE = 9600

# ── Camera ────────────────────────────────────────────────────────────────────
CAMERA_INDEX = 0                    # Default camera device index

# ── ArUco Calibration ─────────────────────────────────────────────────────────
ARUCO_DICT = "DICT_4X4_50"
ARUCO_MARKER_SIZE_MM = 40.0

# Real-world printer-coordinate positions of each ArUco marker (mm).
# Key = marker ID, Value = (X_mm, Y_mm)
ARUCO_MARKER_POSITIONS_MM: dict[int, tuple[float, float]] = {
    0: (10.0, 10.0),    # front-left
    1: (210.0, 10.0),   # front-right
    2: (210.0, 210.0),  # rear-right
    3: (10.0, 210.0),   # rear-left
}

# ── Calibration Storage ───────────────────────────────────────────────────────
CALIBRATION_FILE = "data/calibration.json"
PARTS_DB_FILE = "data/parts_db.json"
UPLOADS_DIR = "data/uploads"
USER_CONFIG_FILE = "data/user_config.json"   # persisted user settings
BACKGROUND_IMAGE_PATH = "data/background.png"

# ── G-code Defaults ───────────────────────────────────────────────────────────
DEFAULT_LINE_SPACING_MM = 1.0
DEFAULT_Z_OFFSET_MM = 0.3
DEFAULT_FEED_RATE = 600           # mm/min — coating move
DEFAULT_TRAVEL_RATE = 1500        # mm/min — empty move
DEFAULT_BAND_THICKNESS_MM = 1.0
DEFAULT_PATTERN_TYPE = "zigzag"   # "zigzag" | "spiral" | "parallel"

# ── ML Model ──────────────────────────────────────────────────────────────────
ML_MODEL_PATH = "ml/models/parts_model.pt"
ML_CONFIDENCE_THRESHOLD = 0.5

# ── Detection ─────────────────────────────────────────────────────────────────
MIN_CONTOUR_AREA_PX = 1000        # pixels² — smaller blobs are ignored


# ── Persistence helpers ───────────────────────────────────────────────────────

def save_user_config() -> None:
    """Persist mutable user settings to USER_CONFIG_FILE."""
    import sys
    mod = sys.modules[__name__]
    data = {
        "printer_port": mod.PRINTER_PORT,
        "printer_baudrate": mod.PRINTER_BAUDRATE,
        "pump_port": mod.PUMP_PORT,
        "pump_baudrate": mod.PUMP_BAUDRATE,
        "camera_index": mod.CAMERA_INDEX,
        "aruco_marker_positions_mm": {
            str(k): list(v)
            for k, v in mod.ARUCO_MARKER_POSITIONS_MM.items()
        },
    }
    os.makedirs(os.path.dirname(USER_CONFIG_FILE), exist_ok=True)
    with open(USER_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_user_config() -> None:
    """Load persisted user settings and override module-level defaults."""
    if not os.path.exists(USER_CONFIG_FILE):
        return
    try:
        with open(USER_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return  # corrupted file → use defaults

    import sys
    mod = sys.modules[__name__]

    simple_keys = {
        "printer_port": "PRINTER_PORT",
        "printer_baudrate": "PRINTER_BAUDRATE",
        "pump_port": "PUMP_PORT",
        "pump_baudrate": "PUMP_BAUDRATE",
        "camera_index": "CAMERA_INDEX",
    }
    for json_key, attr in simple_keys.items():
        if json_key in data:
            setattr(mod, attr, data[json_key])

    if "aruco_marker_positions_mm" in data:
        mod.ARUCO_MARKER_POSITIONS_MM = {
            int(k): tuple(v)
            for k, v in data["aruco_marker_positions_mm"].items()
        }


# Load persisted settings immediately when this module is imported
load_user_config()
