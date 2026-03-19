"""
YOLOv8 inference module.

Loads the trained model (if it exists) and provides a predict_part() helper
that returns (class_name, confidence) for a given frame + bounding box.
Falls back gracefully when the model file is missing.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

# Module-level model cache — loaded once on first call.
_model = None
_model_loaded = False


def _load_model():
    """Load YOLOv8 model from disk. Sets _model to None if not available."""
    global _model, _model_loaded
    if _model_loaded:
        return

    _model_loaded = True
    model_path = config.ML_MODEL_PATH

    if not os.path.exists(model_path):
        _model = None
        return

    try:
        from ultralytics import YOLO
        _model = YOLO(model_path)
    except Exception:
        _model = None


def predict_part(
    frame: np.ndarray,
    bbox: list[int],
) -> tuple[Optional[str], Optional[float]]:
    """
    Run YOLOv8 inference on the region of *frame* defined by *bbox* [x,y,w,h].

    Returns (class_name, confidence), or (None, None) if unavailable.
    """
    _load_model()

    if _model is None:
        return None, None

    x, y, w, h = bbox
    roi = frame[y: y + h, x: x + w]
    if roi.size == 0:
        return None, None

    try:
        results = _model.predict(roi, verbose=False, conf=config.ML_CONFIDENCE_THRESHOLD)
        if not results or not results[0].boxes:
            return None, None

        boxes = results[0].boxes
        # Pick the detection with the highest confidence.
        best_idx = int(boxes.conf.argmax())
        confidence = float(boxes.conf[best_idx])
        class_id = int(boxes.cls[best_idx])
        class_name = results[0].names[class_id]
        return class_name, confidence
    except Exception:
        return None, None


def is_model_available() -> bool:
    """Return True if a trained model file exists on disk."""
    return os.path.exists(config.ML_MODEL_PATH)
