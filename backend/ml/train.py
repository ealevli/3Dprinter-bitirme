"""
YOLOv8 transfer-learning retrain pipeline.

Triggered via POST /parts/retrain.  Expects uploaded part images to be in
config.UPLOADS_DIR, and the parts database to list class names.

The function auto-generates a minimal YOLO dataset structure, then fine-tunes
yolov8n.pt for a small number of epochs.
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Callable, Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


def retrain_model(
    progress_callback: Optional[Callable[[int], None]] = None,
) -> None:
    """
    Build a YOLO dataset from the parts library and retrain.

    *progress_callback* receives integers 0–100 during training.
    Raises RuntimeError if ultralytics is not installed or no data is available.
    """
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("ultralytics paketi yüklü değil: pip install ultralytics") from exc

    # Load parts database.
    if not os.path.exists(config.PARTS_DB_FILE):
        raise RuntimeError("Parça kütüphanesi boş. Önce parça ekleyin.")

    with open(config.PARTS_DB_FILE) as f:
        db = json.load(f)

    parts = [p for p in db.get("parts", []) if p.get("image_path")]
    if not parts:
        raise RuntimeError("Fotoğraflı parça bulunamadı.")

    # Build dataset directory.
    dataset_dir = "ml/dataset"
    images_train = os.path.join(dataset_dir, "images", "train")
    labels_train = os.path.join(dataset_dir, "labels", "train")
    os.makedirs(images_train, exist_ok=True)
    os.makedirs(labels_train, exist_ok=True)

    class_names = sorted({p["name"] for p in parts})
    class_to_idx = {name: i for i, name in enumerate(class_names)}

    # Copy images and generate dummy full-frame labels.
    for part in parts:
        img_src = part["image_path"]
        if not os.path.exists(img_src):
            continue
        ext = os.path.splitext(img_src)[1]
        dst_name = f"{part['id']}{ext}"
        shutil.copy(img_src, os.path.join(images_train, dst_name))

        # YOLO label: class_idx cx cy w h (normalised, full frame = 0.5 0.5 1.0 1.0)
        cls_idx = class_to_idx[part["name"]]
        label_path = os.path.join(labels_train, f"{part['id']}.txt")
        with open(label_path, "w") as lf:
            lf.write(f"{cls_idx} 0.5 0.5 1.0 1.0\n")

    # Write dataset YAML.
    yaml_path = os.path.join(dataset_dir, "dataset.yaml")
    with open(yaml_path, "w") as yf:
        yf.write(f"path: {os.path.abspath(dataset_dir)}\n")
        yf.write("train: images/train\n")
        yf.write("val: images/train\n")  # small dataset → use train as val
        yf.write(f"nc: {len(class_names)}\n")
        yf.write(f"names: {class_names}\n")

    if progress_callback:
        progress_callback(10)

    # Fine-tune.
    model = YOLO("yolov8n.pt")

    def _on_epoch_end(trainer):
        if progress_callback:
            pct = 10 + int(80 * trainer.epoch / trainer.epochs)
            progress_callback(pct)

    model.add_callback("on_train_epoch_end", _on_epoch_end)
    model.train(
        data=yaml_path,
        epochs=30,
        imgsz=320,
        batch=4,
        project="ml",
        name="train",
        exist_ok=True,
        verbose=False,
    )

    # Copy best weights to the canonical path.
    best_weights = "ml/train/weights/best.pt"
    if os.path.exists(best_weights):
        os.makedirs(os.path.dirname(config.ML_MODEL_PATH), exist_ok=True)
        shutil.copy(best_weights, config.ML_MODEL_PATH)

    # Invalidate cached model so next inference reloads.
    import ml.model as _m
    _m._model = None
    _m._model_loaded = False

    if progress_callback:
        progress_callback(100)
