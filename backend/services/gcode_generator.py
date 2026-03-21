"""
G-code generator — Cura-style coating path.

Structure (single layer):
  1. Start sequence  (home, lift, move to start)
  2. WALL-OUTER      (trace part perimeter once)
  3. INFILL          (zigzag / parallel / spiral clipped to polygon)
  4. End sequence    (lift, park)

No extrusion (E) commands — pump is controlled separately via Arduino.
No temperature commands — heater not connected.

Start and end G-code sequences are configurable via DEFAULT_START_GCODE and
DEFAULT_END_GCODE constants. Placeholders are replaced at generation time:
  {part_x}, {part_y}   — first contour point (mm)
  {z_coat}             — coating Z level (mm)
  {z_travel}           — travel Z level (mm)
  {z_travel_end}       — end travel Z level (z_travel + 10 mm)
  {feed_rate}          — coating feed rate (mm/min)
  {travel_rate}        — rapid travel rate (mm/min)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from shapely.geometry import LineString, Polygon

PatternType = Literal["zigzag", "parallel", "spiral"]

# ── Default G-code sequences ──────────────────────────────────────────────────

DEFAULT_START_GCODE = """\
G28 ; Eksenleri sifirla
G90 ; Mutlak konum modu
G0 F{travel_rate} Z{z_travel} ; Nozzle'i kaldir
G0 F{travel_rate} X{part_x} Y{part_y} ; Parca konumuna git"""

DEFAULT_END_GCODE = """\
G0 F300 Z{z_travel_end} ; Nozzle'i yukari kaldir
G0 F{travel_rate} X0 Y220 ; Park pozisyonu
M84 X Y E ; Motorlari devre disi birak (Z hariç)"""


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
    start_gcode: str | None = None,
    end_gcode: str | None = None,
) -> dict:
    """
    Generate coating G-code from a part contour (mm coordinates).

    Args:
        contour_mm  : Part outline in printer mm coordinates.
        params      : Coating parameters. Defaults to CoatingParams().
        start_gcode : Custom start sequence with placeholders. Uses
                      DEFAULT_START_GCODE when None.
        end_gcode   : Custom end sequence with placeholders. Uses
                      DEFAULT_END_GCODE when None.

    Returns:
        gcode          : str   — complete G-code program
        line_count     : int
        estimated_time_s: float
        paths          : list[{x, y}]  — XY moves for canvas preview
        wall_paths     : list[{x, y}]  — perimeter points for preview
    """
    if params is None:
        params = CoatingParams()
    if start_gcode is None:
        start_gcode = DEFAULT_START_GCODE
    if end_gcode is None:
        end_gcode = DEFAULT_END_GCODE

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

    # Compute part_x, part_y from first contour point (or centroid as fallback)
    if contour_mm:
        part_x, part_y = contour_mm[0][0], contour_mm[0][1]
    else:
        c = poly.centroid
        part_x, part_y = c.x, c.y

    z_travel_end = round(zt + 10.0, 3)

    # Build placeholder mapping
    placeholders = {
        "part_x":      f"{part_x:.3f}",
        "part_y":      f"{part_y:.3f}",
        "z_coat":      f"{zc:.3f}",
        "z_travel":    f"{zt:.3f}",
        "z_travel_end": f"{z_travel_end:.3f}",
        "feed_rate":   str(params.feed_rate),
        "travel_rate": str(params.travel_rate),
    }

    def _fill_placeholders(template: str) -> str:
        result = template
        for key, value in placeholders.items():
            result = result.replace("{" + key + "}", value)
        return result

    # ── Header ────────────────────────────────────────────────────────────────
    meta_lines = [
        "; === 3D Printer Coating System — Auto-generated G-code ===",
        f"; Pattern   : {params.pattern_type}",
        f"; Spacing   : {params.line_spacing} mm",
        f"; Z coating : {zc} mm  (tape {params.band_thickness} + offset {params.z_offset})",
        f"; Feed      : {params.feed_rate} mm/min",
        "; ---",
    ]
    start_lines = _fill_placeholders(start_gcode).splitlines()
    header = meta_lines + start_lines

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
    end_lines = _fill_placeholders(end_gcode).splitlines()
    footer = ["; --- End ---"] + end_lines + ["; === End of coating program ==="]

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
