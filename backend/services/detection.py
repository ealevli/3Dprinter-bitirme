"""
Part detection service.

Strategy (in order of attempt):
  A. Two-pass: find bright background (white paper) → find dark part inside it
  B. Direct: find compact dark object in bed ROI (no paper)

Pipeline after finding the contour:
  - approxPolyDP simplification
  - pixel_to_mm transform
  - (Optional) YOLOv8 classification
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from services.calibration import load_calibration, pixel_to_mm, detect_markers


# ── Mask helpers ─────────────────────────────────────────────────────────────

def _build_bed_mask(
    frame: np.ndarray,
    marker_px: dict[int, tuple[float, float]],
    marker_size_px: int = 60,
) -> np.ndarray:
    h, w = frame.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)

    if len(marker_px) >= 2:
        centers = np.array(list(marker_px.values()), dtype=np.float32)
        hull = cv2.convexHull(centers.reshape(-1, 1, 2).astype(np.int32))
        cv2.fillConvexPoly(mask, hull, 255)
        # Black out marker squares themselves
        half = marker_size_px // 2
        for (cx, cy) in marker_px.values():
            x1, y1 = max(0, int(cx)-half), max(0, int(cy)-half)
            x2, y2 = min(w, int(cx)+half), min(h, int(cy)+half)
            mask[y1:y2, x1:x2] = 0
    else:
        # No markers: use centre 70% of frame
        mx0, my0 = int(w*0.15), int(h*0.15)
        mask[my0:int(h*0.85), mx0:int(w*0.85)] = 255

    return mask


def _bed_area_px(marker_px: dict) -> float:
    if len(marker_px) < 2:
        return float("inf")
    centers = np.array(list(marker_px.values()), dtype=np.float32)
    hull = cv2.convexHull(centers.reshape(-1, 1, 2))
    return float(cv2.contourArea(hull))


# ── Detection passes ──────────────────────────────────────────────────────────

def _find_paper_roi(gray: np.ndarray, mask: np.ndarray) -> Optional[tuple[int,int,int,int]]:
    """
    Try to find a bright background (white paper / light surface) in the masked area.
    Returns (x, y, w, h) bounding box or None.
    """
    # Threshold for bright objects (paper is very bright)
    _, bright = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    bright = cv2.bitwise_and(bright, mask)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel)
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN,  kernel)

    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Largest bright region = paper
    paper = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(paper)
    if area < 5000:  # too small to be a paper
        return None

    x, y, w, h = cv2.boundingRect(paper)
    # Add small inset so we don't pick up paper edge artefacts
    pad = 10
    return (x+pad, y+pad, max(1, w-2*pad), max(1, h-2*pad))


def _find_dark_part_in_roi(
    gray: np.ndarray,
    roi: tuple[int,int,int,int],
) -> Optional[np.ndarray]:
    """
    Find the largest compact DARK object inside the given ROI.
    Returns the contour (in full-frame coords) or None.
    """
    x, y, w, h = roi
    if w <= 0 or h <= 0:
        return None

    crop = gray[y:y+h, x:x+w]

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    eq = clahe.apply(crop)
    blurred = cv2.GaussianBlur(eq, (5, 5), 0)

    # Dark objects on bright background
    thresh = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=21, C=6,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    closed = cv2.morphologyEx(closed, cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Score: compact + squarish shape
    best, best_score = None, -1.0
    roi_area = w * h
    for c in contours:
        area = cv2.contourArea(c)
        if area < config.MIN_CONTOUR_AREA_PX or area > roi_area * 0.70:
            continue
        hull_area = cv2.contourArea(cv2.convexHull(c))
        solidity = area / hull_area if hull_area > 0 else 0
        bx, by, bw, bh = cv2.boundingRect(c)
        aspect = max(bw, bh) / max(min(bw, bh), 1)
        aspect_score = 1.0 if aspect < 2.0 else (0.4 if aspect < 3.5 else 0.0)
        score = solidity * aspect_score * area
        if score > best_score:
            best_score = score
            best = c

    if best is None:
        return None

    # Shift contour back to full-frame coordinates
    best_shifted = best + np.array([[[x, y]]])
    return best_shifted


def _find_part_direct(
    gray: np.ndarray,
    mask: np.ndarray,
    bed_area: float,
) -> Optional[np.ndarray]:
    """
    Fallback: find the best compact contour directly in the masked bed area.
    Works when there is no white paper background.
    """
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    eq = clahe.apply(gray)
    blurred = cv2.GaussianBlur(eq, (7, 7), 0)

    thresh = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=21, C=4,
    )
    thresh = cv2.bitwise_and(thresh, mask)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    max_area = bed_area * 0.50

    best, best_score = None, -1.0
    for c in contours:
        area = cv2.contourArea(c)
        if area < config.MIN_CONTOUR_AREA_PX or area > max_area:
            continue
        hull_area = cv2.contourArea(cv2.convexHull(c))
        solidity = area / hull_area if hull_area > 0 else 0
        bx, by, bw, bh = cv2.boundingRect(c)
        aspect = max(bw, bh) / max(min(bw, bh), 1)
        aspect_score = 1.0 if aspect < 2.0 else (0.4 if aspect < 3.5 else 0.0)
        score = solidity * aspect_score * area
        if score > best_score:
            best_score = score
            best = c

    return best


# ── Public API ────────────────────────────────────────────────────────────────

def detect_part(frame: np.ndarray, use_ml: bool = True) -> dict:
    """
    Detect the part in *frame*.

    Returns:
    {
        contour_px, contour_mm, bbox,
        class_name, confidence,
        calibrated, markers_found,
        method,   # "paper_roi" | "direct" | "none"
        error,
    }
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 1. Markers → bed mask
    marker_px = detect_markers(frame)
    markers_found = len(marker_px)
    frame_h, frame_w = frame.shape[:2]
    marker_size_px = max(40, frame_w // 12)
    mask = _build_bed_mask(frame, marker_px, marker_size_px)
    bed_area = _bed_area_px(marker_px)

    # 2a. Try two-pass (paper → dark part inside paper)
    method = "none"
    best_contour = None

    paper_roi = _find_paper_roi(gray, mask)
    if paper_roi is not None:
        best_contour = _find_dark_part_in_roi(gray, paper_roi)
        if best_contour is not None:
            method = "paper_roi"

    # 2b. Fallback: direct search in bed area
    if best_contour is None:
        best_contour = _find_part_direct(gray, mask, bed_area)
        if best_contour is not None:
            method = "direct"

    if best_contour is None:
        return {
            "contour_px": [], "contour_mm": [], "bbox": None,
            "class_name": None, "confidence": None,
            "calibrated": load_calibration() is not None,
            "markers_found": markers_found,
            "method": "none",
            "error": "Parça bulunamadı. Parçayı beyaz kağıt üzerine koy, ışık düzgün olsun.",
        }

    # 3. Simplify contour
    epsilon = 0.008 * cv2.arcLength(best_contour, True)
    approx = cv2.approxPolyDP(best_contour, epsilon, True)
    contour_px = approx.reshape(-1, 2).tolist()
    x, y, w, h = cv2.boundingRect(best_contour)

    # 4. mm conversion
    H = load_calibration()
    calibrated = H is not None
    contour_mm = (
        [list(pixel_to_mm(pt[0], pt[1], H)) for pt in contour_px]
        if calibrated else []
    )

    # 5. Optional ML
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
            pass

    return {
        "contour_px": contour_px, "contour_mm": contour_mm,
        "bbox": [x, y, w, h],
        "class_name": class_name, "confidence": confidence,
        "calibrated": calibrated,
        "markers_found": markers_found,
        "method": method,
        "error": None,
    }


def annotate_frame(frame: np.ndarray, detection: dict) -> np.ndarray:
    out = frame.copy()

    if detection["contour_px"]:
        pts = np.array(detection["contour_px"], dtype=np.int32)
        cv2.polylines(out, [pts], True, (0, 255, 0), 2)

    if detection["bbox"]:
        x, y, w, h = detection["bbox"]
        label = detection["class_name"] or "Parça"
        conf  = detection["confidence"]
        text  = f"{label} ({conf:.2f})" if conf else label
        cv2.rectangle(out, (x, y), (x+w, y+h), (0, 200, 255), 2)
        cv2.putText(out, text, (x, max(y-8, 14)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)

    # Method tag
    method = detection.get("method", "")
    method_label = {"paper_roi": "kagit+parca", "direct": "direkt", "none": ""}.get(method, method)
    if method_label:
        cv2.putText(out, method_label, (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 0), 1)

    # Marker count
    n = detection.get("markers_found", 0)
    color = (0, 255, 0) if n >= 4 else (0, 165, 255) if n > 0 else (0, 0, 255)
    cv2.putText(out, f"Markers: {n}/4",
                (10, out.shape[0]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    if detection.get("error"):
        cv2.putText(out, detection["error"][:55], (10, 44),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 80, 255), 1)

    return out
