"""
G-code generator — Cura-style coating path.

Structure (same as Cura):
  1. Start sequence  (home, lift, move to start)
  2. WALL-OUTER      (trace part perimeter once)
  3. INFILL          (zigzag / parallel / spiral clipped to polygon)
  4. End sequence    (lift, park)

No extrusion (E) commands — pump is controlled separately via Arduino.
No temperature commands — heater not connected.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from shapely.geometry import LineString, Polygon

PatternType = Literal["zigzag", "parallel", "spiral"]


@dataclass
class CoatingParams:
    line_spacing: float = 1.0       # mm between fill lines
    z_offset: float   = 0.3         # mm above part surface
    feed_rate: int    = 600          # mm/min — coating move
    travel_rate: int  = 1500         # mm/min — rapid travel
    band_thickness: float = 1.0      # mm — tape under the part
    pattern_type: PatternType = "zigzag"


# ── Z levels ─────────────────────────────────────────────────────────────────

def _z_coat(p: CoatingParams) -> float:
    """Z during coating (tape + nozzle gap)."""
    return round(p.z_offset + p.band_thickness, 3)

def _z_travel(p: CoatingParams) -> float:
    """Z during rapid travel (coat + 5 mm clearance)."""
    return round(_z_coat(p) + 5.0, 3)


# ── Move helpers ──────────────────────────────────────────────────────────────

def _rapid(x: float, y: float, z: float, fr: int) -> str:
    return f"G0 F{fr} X{x:.3f} Y{y:.3f} Z{z:.3f}"

def _coat_move(x: float, y: float, fr: int) -> str:
    return f"G1 F{fr} X{x:.3f} Y{y:.3f}"

def _z_move(z: float, fr: int = 300) -> str:
    return f"G1 F{fr} Z{z:.3f}"


# ── Wall (perimeter) ──────────────────────────────────────────────────────────

def _wall_lines(poly: Polygon, p: CoatingParams) -> list[str]:
    """Trace the outer perimeter of *poly* once (Cura WALL-OUTER)."""
    coords = list(poly.exterior.coords)
    if not coords:
        return []

    zc = _z_coat(p)
    zt = _z_travel(p)
    fr = p.feed_rate
    tr = p.travel_rate

    lines: list[str] = [
        f"; WALL-OUTER",
        _rapid(coords[0][0], coords[0][1], zt, tr),
        _z_move(zc),
    ]
    for x, y in coords[1:]:
        lines.append(_coat_move(x, y, fr))
    lines.append(_z_move(zt))
    return lines


# ── Fill patterns ─────────────────────────────────────────────────────────────

def _zigzag_lines(poly: Polygon, p: CoatingParams) -> list[str]:
    """Boustrophedon (zigzag) raster fill clipped to *poly*."""
    minx, miny, maxx, maxy = poly.bounds
    zc = _z_coat(p)
    zt = _z_travel(p)
    fr = p.feed_rate
    tr = p.travel_rate

    lines: list[str] = ["; INFILL zigzag"]
    y   = miny
    fwd = True

    while y <= maxy + 1e-9:
        scan = LineString(
            [(minx - 1, y), (maxx + 1, y)] if fwd
            else [(maxx + 1, y), (minx - 1, y)]
        )
        clipped = poly.intersection(scan)

        if not clipped.is_empty:
            segs = (
                [clipped]          if clipped.geom_type == "LineString"
                else list(clipped.geoms) if hasattr(clipped, "geoms")
                else []
            )
            for seg in segs:
                if seg.geom_type != "LineString":
                    continue
                cx = list(seg.coords)
                if len(cx) < 2:
                    continue
                sx, sy = cx[0]
                ex, ey = cx[-1]
                lines.append(_rapid(sx, sy, zt, tr))
                lines.append(_z_move(zc))
                lines.append(_coat_move(ex, ey, fr))
                lines.append(_z_move(zt))

        y   += p.line_spacing
        fwd  = not fwd

    return lines


def _parallel_lines(poly: Polygon, p: CoatingParams) -> list[str]:
    """One-directional parallel lines (always left→right)."""
    minx, miny, maxx, maxy = poly.bounds
    zc = _z_coat(p)
    zt = _z_travel(p)
    fr = p.feed_rate
    tr = p.travel_rate

    lines: list[str] = ["; INFILL parallel"]
    y = miny
    while y <= maxy + 1e-9:
        scan    = LineString([(minx - 1, y), (maxx + 1, y)])
        clipped = poly.intersection(scan)
        if not clipped.is_empty:
            segs = (
                [clipped]          if clipped.geom_type == "LineString"
                else list(clipped.geoms) if hasattr(clipped, "geoms")
                else []
            )
            for seg in segs:
                if seg.geom_type != "LineString":
                    continue
                cx = list(seg.coords)
                if len(cx) < 2:
                    continue
                sx, sy = cx[0]
                ex, ey = cx[-1]
                lines.append(_rapid(sx, sy, zt, tr))
                lines.append(_z_move(zc))
                lines.append(_coat_move(ex, ey, fr))
                lines.append(_z_move(zt))
        y += p.line_spacing
    return lines


def _spiral_lines(poly: Polygon, p: CoatingParams) -> list[str]:
    """Inward-offset spiral (concentric shells)."""
    zc = _z_coat(p)
    zt = _z_travel(p)
    fr = p.feed_rate
    tr = p.travel_rate

    lines: list[str] = ["; INFILL spiral"]
    current = poly
    first   = True

    while not current.is_empty and current.area > 1.0:
        coords = list(current.exterior.coords)
        sx, sy = coords[0]
        lines.append(_rapid(sx, sy, zt, tr))
        lines.append(_z_move(zc))
        for x, y in coords[1:]:
            lines.append(_coat_move(x, y, fr))
        lines.append(_z_move(zt))

        try:
            current = current.buffer(-p.line_spacing)
        except Exception:
            break

    return lines


# ── Public API ────────────────────────────────────────────────────────────────

def generate_gcode(
    contour_mm: list[list[float]],
    params: CoatingParams | None = None,
) -> dict:
    """
    Generate coating G-code from a part contour (mm coordinates).

    Returns:
        gcode          : str   — complete G-code program
        line_count     : int
        estimated_time_s: float
        paths          : list[{x, y}]  — XY moves for canvas preview
        wall_paths     : list[{x, y}]  — perimeter points for preview
    """
    if params is None:
        params = CoatingParams()

    # Build Shapely polygon
    poly = Polygon([(pt[0], pt[1]) for pt in contour_mm])
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or poly.area < 1.0:
        return {
            "gcode": "; ERROR: contour too small or invalid",
            "line_count": 1,
            "estimated_time_s": 0,
            "paths": [],
            "wall_paths": [],
        }

    zt = _z_travel(params)
    zc = _z_coat(params)
    cx_start, cy_start = list(poly.exterior.coords)[0]

    # ── Header ────────────────────────────────────────────────────────────────
    header = [
        "; === 3D Printer Coating System — Auto-generated G-code ===",
        f"; Pattern   : {params.pattern_type}",
        f"; Spacing   : {params.line_spacing} mm",
        f"; Z coating : {zc} mm  (tape {params.band_thickness} + offset {params.z_offset})",
        f"; Feed      : {params.feed_rate} mm/min",
        "; ---",
        "G28",                                          # home all axes
        "G90",                                          # absolute mode
        f"G0 F{params.travel_rate} Z{zt:.3f}",         # lift
        f"G0 F{params.travel_rate} X{cx_start:.3f} Y{cy_start:.3f}",  # move to part
    ]

    # ── Wall ──────────────────────────────────────────────────────────────────
    wall = _wall_lines(poly, params)

    # ── Infill ────────────────────────────────────────────────────────────────
    if params.pattern_type == "spiral":
        fill = _spiral_lines(poly, params)
    elif params.pattern_type == "parallel":
        fill = _parallel_lines(poly, params)
    else:
        fill = _zigzag_lines(poly, params)

    # ── Footer ────────────────────────────────────────────────────────────────
    footer = [
        "; --- End ---",
        f"G0 F300 Z{zt + 10:.3f}",      # raise nozzle high
        "G0 X0 Y220",                    # park (front of bed, like Cura)
        "M84 X Y E",                     # disable steppers (keep Z)
        "; === End of coating program ===",
    ]

    all_lines = header + wall + fill + footer
    gcode_str = "\n".join(all_lines)

    # ── Preview paths ─────────────────────────────────────────────────────────
    # Only collect X/Y from G0/G1 lines (skip comments and Z-only moves)
    def _parse_paths(line_list: list[str]) -> list[dict]:
        pts = []
        for ln in line_list:
            if ln.startswith(";") or not ln.startswith("G"):
                continue
            tok: dict[str, float] = {}
            for t in ln.split():
                if t[0] in "XYZF" and len(t) > 1:
                    try:
                        tok[t[0]] = float(t[1:])
                    except ValueError:
                        pass
            if "X" in tok and "Y" in tok:
                pts.append({"x": tok["X"], "y": tok["Y"]})
        return pts

    wall_paths = _parse_paths(wall)
    fill_paths = _parse_paths(fill)

    # Time estimate: count actual coating moves (G1 with no Z, just XY)
    coating_distance = 0.0
    prev = None
    for pt in fill_paths:
        if prev:
            dx = pt["x"] - prev["x"]
            dy = pt["y"] - prev["y"]
            coating_distance += math.sqrt(dx*dx + dy*dy)
        prev = pt
    estimated_s = (coating_distance / max(params.feed_rate, 1)) * 60

    return {
        "gcode":              gcode_str,
        "line_count":         len(all_lines),
        "estimated_time_s":   round(estimated_s, 1),
        "paths":              fill_paths,
        "wall_paths":         wall_paths,
    }
