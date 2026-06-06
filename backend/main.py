"""
FastAPI entry point for the 3D Printer Coating System.
Registers all routers and configures CORS for the React frontend.
"""

import faulthandler
import logging
import os

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
# Keep noisy third-party loggers quiet
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)
logging.getLogger("multipart").setLevel(logging.WARNING)

# Write C-level crash tracebacks to a file next to the backend log.
_crash_log = os.path.join(os.path.dirname(__file__), "..", "crash.log")
faulthandler.enable(open(_crash_log, "w"), all_threads=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import camera, detection, gcode, pump, parts, system, jog

app = FastAPI(
    title="3D Printer Coating System API",
    version="1.0.0",
    description="Intelligent coating system backed by OpenCV, YOLOv8, and Marlin G-code.",
)

# Allow requests from the Vite dev server and any local origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(camera.router, prefix="/camera", tags=["Camera"])
app.include_router(detection.router, prefix="/detect", tags=["Detection"])
app.include_router(gcode.router, prefix="/gcode", tags=["G-code"])
app.include_router(pump.router, prefix="/pump", tags=["Pump"])
app.include_router(parts.router, prefix="/parts", tags=["Parts Library"])
app.include_router(system.router, prefix="/system", tags=["System"])
app.include_router(jog.router, prefix="/jog", tags=["Jog"])


@app.get("/", tags=["Root"])
async def root() -> dict:
    return {"message": "Coating System API is running."}
