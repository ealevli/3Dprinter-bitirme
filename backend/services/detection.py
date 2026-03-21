"""
Part detection service.

Pipeline:
  1. ArUco markers ile tabla sınırını bul → iç ROI maskesi oluştur
  2. Marker karelerini maskeden çıkar (siyah yap)
  3. ROI içinde: CLAHE → blur → adaptiveThreshold → morphClose
  4. Konturları bul → tabla boyutundakileri elendir → en büyüğü al = parça
  5. approxPolyDP ile sadeleştir
  6. pixel_to_mm ile mm koordinatına çevir
  7. (Opsiyonel) YOLOv8 sınıflandırma
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


# ── Yardımcı fonksiyonlar ────────────────────────────────────────────────────

def _build_bed_mask(
    frame: np.ndarray,
    marker_px: dict[int, tuple[float, float]],
    marker_size_px: int = 60,
) -> np.ndarray:
    """
    Marker konumlarından tabla iç alanını beyaz, dışını siyah yapan maske üretir.
    Marker karelerinin kendileri de siyah (tespit edilmesin diye).
    """
    h, w = frame.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)

    if len(marker_px) < 4:
        # Kalibrasyon yoksa tüm frame kullan
        mask[:] = 255
        return mask

    # Marker merkezleri → convex hull → tabla alanı beyaz
    centers = np.array(
        [marker_px[i] for i in sorted(marker_px)], dtype=np.float32
    )
    hull = cv2.convexHull(centers.reshape(-1, 1, 2).astype(np.int32))
    cv2.fillConvexPoly(mask, hull, 255)

    # Marker karelerini siyah yap (kendi konturları algılanmasın)
    half = marker_size_px // 2
    for (cx, cy) in marker_px.values():
        x1 = max(0, int(cx) - half)
        y1 = max(0, int(cy) - half)
        x2 = min(w, int(cx) + half)
        y2 = min(h, int(cy) + half)
        mask[y1:y2, x1:x2] = 0

    return mask


def _bed_area_px(marker_px: dict) -> float:
    """Marker convex hull'undan hesaplanan tabla piksel alanı."""
    if len(marker_px) < 4:
        return float("inf")
    centers = np.array(list(marker_px.values()), dtype=np.float32)
    hull = cv2.convexHull(centers.reshape(-1, 1, 2))
    return float(cv2.contourArea(hull))


def _threshold_frame(gray: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    İki farklı eşikleme dene, sonuçları OR ile birleştir.
    Parlak/mat yüzeylerde daha güvenilir.
    """
    # CLAHE ile yerel kontrast artır
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    eq = clahe.apply(gray)

    blurred = cv2.GaussianBlur(eq, (7, 7), 0)

    # 1) Adaptive threshold
    t_adapt = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=21, C=4,
    )

    # 2) Canny kenar → dilate
    edges = cv2.Canny(blurred, 30, 100)
    t_canny = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)

    combined = cv2.bitwise_or(t_adapt, t_canny)

    # Mask dışını sil
    combined = cv2.bitwise_and(combined, mask)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
    return closed


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
        "markers_found": int,           # kaç marker tespit edildi
        "error":       str | None,
    }
    """
    # ── 1. ArUco marker tespiti ──────────────────────────────────────────────
    marker_px = detect_markers(frame)
    markers_found = len(marker_px)

    # ── 2. Maske oluştur ─────────────────────────────────────────────────────
    # Marker boyutunu piksele dönüştür (yaklaşık: frame genişliğine göre)
    frame_w = frame.shape[1]
    marker_size_px = max(40, frame_w // 12)  # adaptif tahmin
    mask = _build_bed_mask(frame, marker_px, marker_size_px)

    bed_area = _bed_area_px(marker_px)

    # ── 3. Eşikleme ──────────────────────────────────────────────────────────
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    closed = _threshold_frame(gray, mask)

    # ── 4. Kontur bulma ──────────────────────────────────────────────────────
    contours, _ = cv2.findContours(
        closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    # Filtreler:
    #   a) Minimum alan (gürültü elendirir)
    #   b) Maksimum alan: tabladan küçük olmalı (tabla kendisi algılanmasın)
    #      Tabla alanının %80'inden küçük olanları al
    max_area = bed_area * 0.80 if bed_area < float("inf") else float("inf")

    valid = [
        c for c in contours
        if config.MIN_CONTOUR_AREA_PX <= cv2.contourArea(c) <= max_area
    ]

    if not valid:
        return {
            "contour_px": [],
            "contour_mm": [],
            "bbox": None,
            "class_name": None,
            "confidence": None,
            "calibrated": load_calibration() is not None,
            "markers_found": markers_found,
            "error": "Parça bulunamadı. Parçanın arka plandan yeterince ayrıştığından emin ol.",
        }

    # En büyük geçerli kontur = parça
    largest = max(valid, key=cv2.contourArea)
    epsilon = 0.005 * cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, epsilon, True)

    contour_px = approx.reshape(-1, 2).tolist()
    x, y, w, h = cv2.boundingRect(largest)

    # ── 5. mm'ye dönüştür ────────────────────────────────────────────────────
    H = load_calibration()
    calibrated = H is not None
    if calibrated:
        contour_mm = [list(pixel_to_mm(pt[0], pt[1], H)) for pt in contour_px]
    else:
        contour_mm = []

    # ── 6. Opsiyonel ML ─────────────────────────────────────────────────────
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
        "contour_px": contour_px,
        "contour_mm": contour_mm,
        "bbox": [x, y, w, h],
        "class_name": class_name,
        "confidence": confidence,
        "calibrated": calibrated,
        "markers_found": markers_found,
        "error": None,
    }


def annotate_frame(frame: np.ndarray, detection: dict) -> np.ndarray:
    """Draw detection results on a copy of *frame* and return it."""
    annotated = frame.copy()

    # Parça konturu
    if detection["contour_px"]:
        pts = np.array(detection["contour_px"], dtype=np.int32)
        cv2.polylines(annotated, [pts], isClosed=True, color=(0, 255, 0), thickness=2)

    # Bounding box + etiket
    if detection["bbox"]:
        x, y, w, h = detection["bbox"]
        label = detection["class_name"] or "Parça"
        conf = detection["confidence"]
        text = f"{label} ({conf:.2f})" if conf else label
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 200, 255), 2)
        cv2.putText(
            annotated, text, (x, max(y - 8, 12)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2,
        )

    # Marker sayısı overlay
    n = detection.get("markers_found", 0)
    color = (0, 255, 0) if n >= 4 else (0, 165, 255) if n > 0 else (0, 0, 255)
    cv2.putText(
        annotated, f"Markers: {n}/4",
        (10, annotated.shape[0] - 10),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2,
    )

    # Hata mesajı
    if detection.get("error"):
        cv2.putText(
            annotated, detection["error"][:60],
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1,
        )

    return annotated
