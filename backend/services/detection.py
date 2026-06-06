"""
Part detection service.

Strategy:
  1. paper_roi  — find genuine white paper (R>170 AND G>170 AND B>170)
                  then find anything non-white inside it.
                  Handles any color part on white background.

  2. direct     — no paper. Compute bed background color as the median of
                  all masked pixels, then find blobs that differ from it.
                  Handles any color part directly on the print bed.

Contour post-processing:
  - Always take convex hull (removes jagged noise)
  - approxPolyDP with gentle epsilon
  - Fallback to minAreaRect 4-corner box if fewer than 4 points remain
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

# Downscale all CV operations to this width for speed.
# Contour coordinates are scaled back to original resolution before returning.
_MAX_DETECT_W = 640


# ── Bed mask ──────────────────────────────────────────────────────────────────

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
        half = marker_size_px // 2
        for (cx, cy) in marker_px.values():
            x1 = max(0, int(cx) - half)
            y1 = max(0, int(cy) - half)
            x2 = min(w, int(cx) + half)
            y2 = min(h, int(cy) + half)
            mask[y1:y2, x1:x2] = 0
    else:
        mx0, my0 = int(w * 0.15), int(h * 0.15)
        mask[my0:int(h * 0.85), mx0:int(w * 0.85)] = 255
    return mask


def _bed_area_px(marker_px: dict) -> float:
    if len(marker_px) < 2:
        return float("inf")
    centers = np.array(list(marker_px.values()), dtype=np.float32)
    hull = cv2.convexHull(centers.reshape(-1, 1, 2))
    return float(cv2.contourArea(hull))


# ── Shared contour picker ─────────────────────────────────────────────────────

def _best_contour(contours, min_area: int, max_area: float) -> Optional[np.ndarray]:
    """Return the most solid, compact, reasonably-sized contour."""
    best, best_score = None, -1.0
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area or area > max_area:
            continue
        hull_area = cv2.contourArea(cv2.convexHull(c))
        solidity = area / hull_area if hull_area > 0 else 0
        bx, by, bw, bh = cv2.boundingRect(c)
        aspect = max(bw, bh) / max(min(bw, bh), 1)
        if aspect > 5.0:
            continue
        aspect_score = 1.0 if aspect < 2.0 else (0.5 if aspect < 3.5 else 0.1)
        score = (solidity ** 2) * aspect_score * area
        if score > best_score:
            best_score = score
            best = c
    return best


def _morph_clean(img: np.ndarray, close_k: int = 9, open_k: int = 5) -> np.ndarray:
    kc = cv2.getStructuringElement(cv2.MORPH_RECT, (close_k, close_k))
    ko = cv2.getStructuringElement(cv2.MORPH_RECT, (open_k, open_k))
    img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kc)
    img = cv2.morphologyEx(img, cv2.MORPH_OPEN, ko)
    return img


def _otsu_threshold(values: np.ndarray) -> float:
    """Pure-numpy Otsu threshold — avoids cv2.threshold on 1D arrays (segfault risk)."""
    hist = np.bincount(values.ravel(), minlength=256).astype(np.float64)
    total = hist.sum()
    if total == 0:
        return 25.0
    hist /= total
    bins = np.arange(256, dtype=np.float64)
    best_thresh, best_var = 0, 0.0
    w0 = 0.0
    mu0_sum = 0.0
    for t in range(256):
        w0 += hist[t]
        mu0_sum += t * hist[t]
        w1 = 1.0 - w0
        if w0 < 1e-10 or w1 < 1e-10:
            continue
        mu0 = mu0_sum / w0
        mu1 = (np.dot(bins, hist) - mu0_sum) / w1
        var = w0 * w1 * (mu0 - mu1) ** 2
        if var > best_var:
            best_var = var
            best_thresh = t
    return float(best_thresh)


# ── Pass A: white paper + non-white part ─────────────────────────────────────

def _find_paper_roi(frame: np.ndarray, mask: np.ndarray) -> Optional[tuple]:
    """Find a genuinely white region (paper). Rejects colored objects."""
    b, g, r = frame[:, :, 0], frame[:, :, 1], frame[:, :, 2]
    white = (
        (b.astype(np.int16) > 170) &
        (g.astype(np.int16) > 170) &
        (r.astype(np.int16) > 170)
    ).astype(np.uint8) * 255
    white = cv2.bitwise_and(white, mask)
    white = _morph_clean(white, close_k=11, open_k=9)

    contours, _ = cv2.findContours(white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    paper = max(contours, key=cv2.contourArea)
    if cv2.contourArea(paper) < 8000:
        return None
    x, y, w, h = cv2.boundingRect(paper)
    pad = 12
    return (x + pad, y + pad, max(1, w - 2 * pad), max(1, h - 2 * pad))


def _find_part_in_roi(frame: np.ndarray, roi: tuple) -> Optional[np.ndarray]:
    """Find anything non-white inside the paper ROI."""
    x, y, w, h = roi
    if w <= 0 or h <= 0:
        return None
    crop = frame[y:y + h, x:x + w].astype(np.float32)
    dist = np.sqrt(
        (255 - crop[:, :, 0]) ** 2 +
        (255 - crop[:, :, 1]) ** 2 +
        (255 - crop[:, :, 2]) ** 2
    )
    dist_u8 = np.clip(dist / 441.0 * 255, 0, 255).astype(np.uint8)
    blurred = cv2.GaussianBlur(dist_u8, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 40, 255, cv2.THRESH_BINARY)
    thresh = _morph_clean(thresh, close_k=7, open_k=5)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = _best_contour(contours, min_area=500, max_area=w * h * 0.85)
    if best is None:
        return None
    return best + np.array([[[x, y]]])
# ── Pass B: background subtraction ────────────────────────────────────────────

def _find_part_bg_subtraction(
    frame: np.ndarray,
    mask: np.ndarray,
    bed_area: float,
) -> Optional[np.ndarray]:
    """
    Background subtraction pass. Load the saved background frame, compute absolute
    difference, threshold, and find contours.
    """
    if not os.path.exists(config.BACKGROUND_IMAGE_PATH):
        return None

    bg = cv2.imread(config.BACKGROUND_IMAGE_PATH)
    if bg is None:
        return None

    # Ensure background matches the current frame size
    if bg.shape != frame.shape:
        bg = cv2.resize(bg, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_AREA)

    f = frame.astype(np.float32)
    b = bg.astype(np.float32)

    # Euclidean distance in BGR space
    dist = np.sqrt(
        (f[:, :, 0] - b[:, :, 0]) ** 2 +
        (f[:, :, 1] - b[:, :, 1]) ** 2 +
        (f[:, :, 2] - b[:, :, 2]) ** 2
    )
    dist_u8 = np.clip(dist / 441.0 * 255, 0, 255).astype(np.uint8)
    blurred = cv2.GaussianBlur(dist_u8, (7, 7), 0)

    # Use Otsu's method on the masked bed area to find the optimal difference threshold
    diff_vals = blurred[mask > 0]
    if len(diff_vals) > 100:
        threshold = max(15.0, min(_otsu_threshold(diff_vals), 50.0))
    else:
        threshold = 25.0

    _, thresh = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY)
    
    thresh = cv2.bitwise_and(thresh, mask)
    # Use larger close kernel to fill gaps caused by glare/reflections
    thresh = _morph_clean(thresh, close_k=15, open_k=5)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return _best_contour(contours, min_area=config.MIN_CONTOUR_AREA_PX, max_area=bed_area * 0.80)


# ── Pass C: direct on bed ─────────────────────────────────────────────────────

def _find_part_direct(
    frame: np.ndarray,
    mask: np.ndarray,
    bed_area: float,
) -> Optional[np.ndarray]:
    """
    No paper. Use the median of all masked bed pixels as background color,
    then find blobs that differ significantly from it.
    Works for any object color (grey, red, dark) on the bed.
    """
    bed_pixels = frame[mask > 0]
    if len(bed_pixels) < 100:
        return None
    bg = np.median(bed_pixels, axis=0).astype(np.float32)  # median BGR

    f = frame.astype(np.float32)
    dist = np.sqrt(
        (f[:, :, 0] - bg[0]) ** 2 +
        (f[:, :, 1] - bg[1]) ** 2 +
        (f[:, :, 2] - bg[2]) ** 2
    )
    dist_u8 = np.clip(dist / 441.0 * 255, 0, 255).astype(np.uint8)
    blurred = cv2.GaussianBlur(dist_u8, (7, 7), 0)

    # Mask out glare (very bright pixels) before computing threshold —
    # otherwise glare dominates Otsu and grey/dark parts fall below the cut.
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    glare_mask = (gray < 210).astype(np.uint8) * 255
    no_glare = cv2.bitwise_and(blurred, glare_mask)

    # Compute Otsu threshold on glare-free pixels only
    masked_vals = no_glare[mask > 0]
    if len(masked_vals) > 100:
        threshold = min(_otsu_threshold(masked_vals), 60.0)
    else:
        threshold = 35.0

    _, thresh = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY)
    thresh = cv2.bitwise_and(thresh, mask)
    thresh = cv2.bitwise_and(thresh, glare_mask)  # also exclude glare blobs
    thresh = _morph_clean(thresh, close_k=9, open_k=7)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return _best_contour(contours, min_area=config.MIN_CONTOUR_AREA_PX, max_area=bed_area * 0.70)


# ── Contour post-processing ───────────────────────────────────────────────────

def _clean_contour(raw: np.ndarray) -> np.ndarray:
    """Convex hull → approxPolyDP → fallback to minAreaRect 4-box."""
    hull = cv2.convexHull(raw)
    epsilon = 0.02 * cv2.arcLength(hull, True)
    approx = cv2.approxPolyDP(hull, epsilon, True)
    
    if len(approx) < 4:
        rect = cv2.minAreaRect(raw)
        box = cv2.boxPoints(rect)
        approx = box.reshape(-1, 1, 2).astype(np.int32)
        
    return approx


# ── Public API ────────────────────────────────────────────────────────────────

def detect_part(frame: np.ndarray, use_ml: bool = False) -> dict:
    frame_h, frame_w = frame.shape[:2]

    # Downscale for fast CV processing; scale results back at the end.
    if frame_w > _MAX_DETECT_W:
        scale = _MAX_DETECT_W / frame_w
        small = cv2.resize(frame, (_MAX_DETECT_W, int(frame_h * scale)),
                           interpolation=cv2.INTER_AREA)
    else:
        scale = 1.0
        small = frame

    sh, sw = small.shape[:2]
    marker_px = detect_markers(small)
    markers_found = len(marker_px)
    marker_size_px = max(40, sw // 12)
    mask = _build_bed_mask(small, marker_px, marker_size_px)
    bed_area = _bed_area_px(marker_px)

    method = "none"
    raw_contour = None

    # Pass A: Background Subtraction (Preferred)
    raw_contour = _find_part_bg_subtraction(small, mask, bed_area)
    if raw_contour is not None:
        method = "bg_sub"

    # Pass B: Paper ROI
    if raw_contour is None:
        paper_roi = _find_paper_roi(small, mask)
        if paper_roi is not None:
            raw_contour = _find_part_in_roi(small, paper_roi)
            if raw_contour is not None:
                method = "paper_roi"

    # Pass C: Direct
    if raw_contour is None:
        raw_contour = _find_part_direct(small, mask, bed_area)
        if raw_contour is not None:
            method = "direct"

    if raw_contour is None:
        return {
            "contour_px": [], "contour_mm": [], "bbox": None,
            "class_name": None, "confidence": None,
            "calibrated": load_calibration() is not None,
            "markers_found": markers_found,
            "method": "none",
            "error": "Parca bulunamadi. Beyaz kagit uzerine koy veya isigi ayarla.",
        }

    approx = _clean_contour(raw_contour)

    # Scale contour and bbox back to original frame coordinates.
    if scale != 1.0:
        inv = 1.0 / scale
        contour_px = [[int(x * inv), int(y * inv)]
                      for x, y in approx.reshape(-1, 2).tolist()]
        xs, ys, ws, hs = cv2.boundingRect(raw_contour)
        x, y, w, h = int(xs * inv), int(ys * inv), int(ws * inv), int(hs * inv)
    else:
        contour_px = approx.reshape(-1, 2).tolist()
        x, y, w, h = cv2.boundingRect(raw_contour)

    H = load_calibration()
    calibrated = H is not None
    contour_mm = (
        [list(pixel_to_mm(pt[0], pt[1], H)) for pt in contour_px]
        if calibrated else []
    )

    class_name: Optional[str] = None
    confidence: Optional[float] = None
    if use_ml and calibrated and os.path.exists(config.ML_MODEL_PATH):
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
        label = detection["class_name"] or "Parca"
        conf = detection["confidence"]
        text = f"{label} ({conf:.2f})" if conf else label
        cv2.rectangle(out, (x, y), (x + w, y + h), (0, 200, 255), 2)
        cv2.putText(out, text, (x, max(y - 8, 14)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
    method = detection.get("method", "")
    if method and method != "none":
        cv2.putText(out, method, (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 0), 1)
    n = detection.get("markers_found", 0)
    color = (0, 255, 0) if n >= 4 else (0, 165, 255) if n > 0 else (0, 0, 255)
    cv2.putText(out, f"Markers: {n}/4", (10, out.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    if detection.get("error"):
        cv2.putText(out, detection["error"][:60], (10, 44),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 80, 255), 1)
    return out
