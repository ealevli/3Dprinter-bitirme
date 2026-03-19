"""
ArUco-based camera calibration service.

Detects 4 ArUco markers on the printer bed and computes a homography matrix
that maps camera pixels → printer mm coordinates.
"""

import json
import os
from typing import Optional

import cv2
import numpy as np

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


def _aruco_detector() -> cv2.aruco.ArucoDetector:
    """Create an ArucoDetector for the dictionary defined in config."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(
        getattr(cv2.aruco, config.ARUCO_DICT)
    )
    params = cv2.aruco.DetectorParameters()
    return cv2.aruco.ArucoDetector(aruco_dict, params)


def detect_markers(
    frame: np.ndarray,
) -> dict[int, tuple[float, float]]:
    """
    Detect ArUco markers in *frame*.

    Returns a dict mapping marker_id → (pixel_cx, pixel_cy).
    """
    detector = _aruco_detector()
    corners, ids, _ = detector.detectMarkers(frame)
    result: dict[int, tuple[float, float]] = {}

    if ids is None:
        return result

    for corner_group, marker_id in zip(corners, ids.flatten()):
        pts = corner_group[0]  # shape (4, 2)
        cx = float(pts[:, 0].mean())
        cy = float(pts[:, 1].mean())
        result[int(marker_id)] = (cx, cy)

    return result


def compute_homography(
    pixel_points: dict[int, tuple[float, float]],
    real_points: Optional[dict[int, tuple[float, float]]] = None,
) -> Optional[np.ndarray]:
    """
    Compute the homography matrix H from pixel coords to mm coords.

    *pixel_points*: {marker_id: (px, py)}
    *real_points*:  {marker_id: (x_mm, y_mm)}  — defaults to config values.

    Returns the 3×3 matrix, or None if fewer than 4 matching markers are found.
    """
    if real_points is None:
        real_points = config.ARUCO_MARKER_POSITIONS_MM

    common_ids = sorted(set(pixel_points) & set(real_points))
    if len(common_ids) < 4:
        return None

    src = np.array([pixel_points[i] for i in common_ids], dtype=np.float32)
    dst = np.array([real_points[i] for i in common_ids], dtype=np.float32)

    H, _ = cv2.findHomography(src, dst)
    return H


def pixel_to_mm(
    px: float, py: float, H: np.ndarray
) -> tuple[float, float]:
    """Transform a pixel coordinate to printer mm using homography matrix H."""
    pt = np.array([px, py, 1.0], dtype=np.float64)
    result = H @ pt
    return float(result[0] / result[2]), float(result[1] / result[2])


# ── Persistence ───────────────────────────────────────────────────────────────

def save_calibration(H: np.ndarray) -> None:
    """Persist the homography matrix to disk."""
    os.makedirs(os.path.dirname(config.CALIBRATION_FILE) or ".", exist_ok=True)
    data = {"homography": H.tolist()}
    with open(config.CALIBRATION_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_calibration() -> Optional[np.ndarray]:
    """Load and return the saved homography matrix, or None if not found."""
    if not os.path.exists(config.CALIBRATION_FILE):
        return None
    with open(config.CALIBRATION_FILE) as f:
        data = json.load(f)
    return np.array(data["homography"], dtype=np.float64)


def run_calibration(frame: np.ndarray) -> dict:
    """
    Full calibration pipeline: detect markers → compute H → save.

    Returns a result dict with keys: success, matrix (list), error (str).
    """
    pixel_pts = detect_markers(frame)
    H = compute_homography(pixel_pts)

    if H is None:
        found = list(pixel_pts.keys())
        return {
            "success": False,
            "matrix": None,
            "error": f"Yeterli marker bulunamadı. Bulunan ID'ler: {found}",
        }

    save_calibration(H)
    return {
        "success": True,
        "matrix": H.tolist(),
        "error": None,
    }
