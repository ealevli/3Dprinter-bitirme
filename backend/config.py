"""
Configuration module for the 3D Printer Coating System.
All hardware-specific settings are centralized here — never hardcode these elsewhere.
"""

# ── Serial Ports ──────────────────────────────────────────────────────────────
PRINTER_PORT = "/dev/ttyUSB0"       # Linux default; Windows: "COM4"
PRINTER_BAUDRATE = 115200

PUMP_PORT = "/dev/ttyACM0"          # Linux default; Windows: "COM3"
PUMP_BAUDRATE = 9600

# ── Camera ────────────────────────────────────────────────────────────────────
CAMERA_INDEX = 0                    # Default camera device index

# ── ArUco Calibration ─────────────────────────────────────────────────────────
ARUCO_DICT = "DICT_4X4_50"
ARUCO_MARKER_SIZE_MM = 30.0

# Real-world printer-coordinate positions of each ArUco marker (mm).
# Key = marker ID, Value = (X_mm, Y_mm)
# These can be overridden via the Settings page (POST /system/config).
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
