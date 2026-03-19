"""
Parts library router — CRUD for saved parts + ML retrain trigger.

Endpoints:
  GET    /parts                 → list all parts
  POST   /parts                 → add new part (multipart: image + JSON)
  PUT    /parts/{part_id}       → update part
  DELETE /parts/{part_id}       → delete part
  POST   /parts/retrain         → trigger ML retrain (async)
  GET    /parts/retrain/status  → retrain job status
"""

import json
import os
import shutil
import time
import threading
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

router = APIRouter()

# ── Simple JSON database ──────────────────────────────────────────────────────

def _load_db() -> dict:
    if not os.path.exists(config.PARTS_DB_FILE):
        return {"parts": []}
    with open(config.PARTS_DB_FILE) as f:
        return json.load(f)


def _save_db(db: dict) -> None:
    os.makedirs(os.path.dirname(config.PARTS_DB_FILE) or ".", exist_ok=True)
    with open(config.PARTS_DB_FILE, "w") as f:
        json.dump(db, f, indent=2)


# ── Retrain state ─────────────────────────────────────────────────────────────

_retrain_status: dict = {"status": "idle", "progress": 0, "error": None}


class DefaultParams(BaseModel):
    line_spacing: float = 1.0
    z_offset: float = 0.3
    feed_rate: int = 600
    pattern_type: str = "zigzag"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_parts():
    db = _load_db()
    return {"parts": db["parts"]}


@router.post("")
async def add_part(
    name: str = Form(...),
    default_params: str = Form("{}"),
    image: Optional[UploadFile] = File(None),
):
    db = _load_db()
    part_id = str(uuid.uuid4())[:8]

    # Save uploaded image.
    image_path: Optional[str] = None
    if image:
        os.makedirs(config.UPLOADS_DIR, exist_ok=True)
        ext = os.path.splitext(image.filename or "")[1] or ".jpg"
        image_path = os.path.join(config.UPLOADS_DIR, f"{part_id}{ext}")
        with open(image_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

    try:
        params = json.loads(default_params)
    except json.JSONDecodeError:
        params = {}

    part = {
        "id": part_id,
        "name": name,
        "image_path": image_path,
        "default_params": params,
        "created_at": time.time(),
    }
    db["parts"].append(part)
    _save_db(db)
    return part


@router.put("/{part_id}")
async def update_part(part_id: str, updates: dict):
    db = _load_db()
    for part in db["parts"]:
        if part["id"] == part_id:
            part.update({k: v for k, v in updates.items() if k != "id"})
            _save_db(db)
            return part
    raise HTTPException(status_code=404, detail="Parça bulunamadı.")


@router.delete("/{part_id}")
async def delete_part(part_id: str):
    db = _load_db()
    for i, part in enumerate(db["parts"]):
        if part["id"] == part_id:
            removed = db["parts"].pop(i)
            # Remove image file if present.
            if removed.get("image_path") and os.path.exists(removed["image_path"]):
                os.remove(removed["image_path"])
            _save_db(db)
            return {"message": "Parça silindi."}
    raise HTTPException(status_code=404, detail="Parça bulunamadı.")


@router.post("/retrain")
async def retrain():
    """Trigger a YOLOv8 retrain job in the background."""
    global _retrain_status
    if _retrain_status["status"] == "running":
        raise HTTPException(status_code=409, detail="Eğitim zaten devam ediyor.")

    def _run():
        global _retrain_status
        _retrain_status = {"status": "running", "progress": 0, "error": None}
        try:
            from ml.train import retrain_model
            retrain_model(progress_callback=lambda p: _retrain_status.update({"progress": p}))
            _retrain_status = {"status": "done", "progress": 100, "error": None}
        except Exception as exc:
            _retrain_status = {"status": "error", "progress": 0, "error": str(exc)}

    threading.Thread(target=_run, daemon=True).start()
    return {"message": "Eğitim başlatıldı."}


@router.get("/retrain/status")
async def retrain_status():
    return _retrain_status
