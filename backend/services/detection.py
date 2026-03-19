"""
Part detection service.

Pipeline:
  1. Grayscale + GaussianBlur
  2. Adaptive threshold
  3. Morphological closing
  4. Find contours → largest one = part
  5. approxPolyDP simplification
  6. pixel_to_mm transform on every point
  7. (Optional) YOLOv8 classification
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from services.calibration import load_calibration, pixel_to_mm


def detect_part(
    frame: np.ndarray,
    use_ml: bool = True,
) -> dict:
    """
    Detect the part in *frame* and return a result dict:

    {
        "contour_px":  [[x, y], ...],   # raw pixel contour
        "contour_mm":  [[x, y], ...],   # converted to printer mm (if calibrated)
        "bbox":        [x, y, w, h],    # bounding box in pixels
        "class_name":  str | None,
        "confidence":  float | None,
        "calibrated":  bool,
    }
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    thresh = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=11, C=2,
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(
        closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    # Filter by minimum area and pick the largest.
    valid = [c for c in contours if cv2.contourArea(c) >= config.MIN_CONTOUR_AREA_PX]
    if not valid:
        return {
            "contour_px": [],
            "contour_mm": [],
            "bbox": None,
            "class_name": None,
            "confidence": None,
            "calibrated": False,
        }

    largest = max(valid, key=cv2.contourArea)
    epsilon = 0.005 * cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, epsilon, True)

    contour_px = approx.reshape(-1, 2).tolist()
    x, y, w, h = cv2.boundingRect(largest)

    # Convert to mm if calibrated.
    H = load_calibration()
    calibrated = H is not None
    if calibrated:
        contour_mm = [list(pixel_to_mm(pt[0], pt[1], H)) for pt in contour_px]
    else:
        contour_mm = []

    # Optional ML classification.
    class_name: Optional[str] = None
    confidence: Optional[float] = None

    if use_ml and calibrated:
        try:
            from ml.model import predict_part
            class_name, confidence = predict_part(frame, [x, y, w, h])
            if confidence is not None and confidence < config.ML_CONFIDENCE_THRESHOLD:
                class_name = None
                confidence = None
        except Exception:
            pass  # ML not available → silently fall back

    return {
        "contour_px": contour_px,
        "contour_mm": contour_mm,
        "bbox": [x, y, w, h],
        "class_name": class_name,
        "confidence": confidence,
        "calibrated": calibrated,
    }


def annotate_frame(frame: np.ndarray, detection: dict) -> np.ndarray:
    """Draw detection results on a copy of *frame* and return it."""
    annotated = frame.copy()
    if detection["contour_px"]:
        pts = np.array(detection["contour_px"], dtype=np.int32)
        cv2.polylines(annotated, [pts], isClosed=True, color=(0, 255, 0), thickness=2)

    if detection["bbox"]:
        x, y, w, h = detection["bbox"]
        label = detection["class_name"] or "Parça"
        conf = detection["confidence"]
        text = f"{label} ({conf:.2f})" if conf else label
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 200, 255), 1)
        cv2.putText(
            annotated, text, (x, y - 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1,
        )

    return annotated
