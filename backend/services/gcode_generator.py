"""
G-code generator service.

Takes a part contour in printer mm coordinates and produces a coating G-code
program using the requested fill pattern (zigzag / parallel / spiral).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from shapely.geometry import LineString, MultiLineString, Polygon


PatternType = Literal["zigzag", "parallel", "spiral"]


@dataclass
class CoatingParams:
    line_spacing: float = 1.0       # mm between fill lines
    z_offset: float = 0.3           # mm above surface
    feed_rate: int = 600            # mm/min — coating move
    travel_rate: int = 1500         # mm/min — travel move
    band_thickness: float = 1.0     # mm — double-sided tape height
    pattern_type: PatternType = "zigzag"


def _safe_z(params: CoatingParams) -> float:
    """Z height during coating move (tape + offset)."""
    return params.z_offset + params.band_thickness


def _travel_z(params: CoatingParams) -> float:
    """Z height during travel (lifted 2 mm above coating)."""
    return _safe_z(params) + 2.0


def _generate_zigzag(poly: Polygon, params: CoatingParams) -> list[str]:
    """Raster fill lines clipped to *poly*."""
    minx, miny, maxx, maxy = poly.bounds
    z_coat = _safe_z(params)
    z_trav = _travel_z(params)
    fr = params.feed_rate
    tr = params.travel_rate

    lines: list[str] = []
    y = miny
    direction = 1

    while y <= maxy + 1e-6:
        if direction == 1:
            scan = LineString([(minx - 1, y), (maxx + 1, y)])
        else:
            scan = LineString([(maxx + 1, y), (minx - 1, y)])

        clipped = poly.intersection(scan)

        if not clipped.is_empty:
            # intersection can return Point / MultiPoint / GeometryCollection —
            # only process LineString segments
            if clipped.geom_type == "LineString":
                segments = [clipped]
            elif hasattr(clipped, "geoms"):
                segments = list(clipped.geoms)
            else:
                segments = []
            for seg in segments:
                if seg.geom_type != "LineString":
                    continue
                coords = list(seg.coords)
                sx, sy = coords[0]
                ex, ey = coords[-1]
                lines.append(f"G1 X{sx:.2f} Y{sy:.2f} Z{z_trav:.2f} F{tr}")
                lines.append(f"G1 Z{z_coat:.2f} F300")
                lines.append(f"G1 X{ex:.2f} Y{ey:.2f} F{fr}")
                lines.append(f"G1 Z{z_trav:.2f} F300")

        y += params.line_spacing
        direction *= -1

    return lines


def _generate_spiral(poly: Polygon, params: CoatingParams) -> list[str]:
    """Inward offset spiral fill."""
    z_coat = _safe_z(params)
    z_trav = _travel_z(params)
    fr = params.feed_rate
    tr = params.travel_rate

    lines: list[str] = []
    current = poly
    first = True

    while not current.is_empty and current.area > 1.0:
        coords = list(current.exterior.coords)
        sx, sy = coords[0]

        if first:
            lines.append(f"G1 X{sx:.2f} Y{sy:.2f} Z{z_trav:.2f} F{tr}")
            lines.append(f"G1 Z{z_coat:.2f} F300")
            first = False
        else:
            lines.append(f"G1 X{sx:.2f} Y{sy:.2f} Z{z_trav:.2f} F{tr}")
            lines.append(f"G1 Z{z_coat:.2f} F300")

        for x, y in coords[1:]:
            lines.append(f"G1 X{x:.2f} Y{y:.2f} F{fr}")

        lines.append(f"G1 Z{z_trav:.2f} F300")

        try:
            current = current.buffer(-params.line_spacing)
        except Exception:
            break

    return lines


def generate_gcode(
    contour_mm: list[list[float]],
    params: CoatingParams | None = None,
) -> dict:
    """
    Generate coating G-code from a contour in mm coordinates.

    Returns:
        {
            "gcode": str,
            "line_count": int,
            "estimated_time_s": float,
            "paths": [{"x": float, "y": float}, ...]   # for canvas preview
        }
    """
    if params is None:
        params = CoatingParams()

    poly = Polygon([(pt[0], pt[1]) for pt in contour_mm])
    if not poly.is_valid:
        poly = poly.buffer(0)

    z_trav = _travel_z(params)

    header = [
        "G28",                            # home all axes
        "G90",                            # absolute positioning
        f"G1 Z{z_trav:.2f} F300",        # lift nozzle
    ]

    if params.pattern_type == "spiral":
        fill_lines = _generate_spiral(poly, params)
    else:
        fill_lines = _generate_zigzag(poly, params)

    footer = [
        f"G1 Z{z_trav + 8:.2f} F300",   # raise nozzle
        "G28 X Y",                        # park X/Y
    ]

    all_lines = header + fill_lines + footer
    gcode_str = "\n".join(all_lines)

    # Rough time estimate (distance / feed_rate).
    total_dist_mm = len(fill_lines) * 10  # very rough
    estimated_s = (total_dist_mm / params.feed_rate) * 60

    # Preview paths: parse X/Y from G1 lines.
    paths: list[dict] = []
    for line in fill_lines:
        parts_map: dict[str, float] = {}
        for token in line.split():
            if token.startswith(("X", "Y", "Z", "F")):
                try:
                    parts_map[token[0]] = float(token[1:])
                except ValueError:
                    pass
        if "X" in parts_map and "Y" in parts_map:
            paths.append({"x": parts_map["X"], "y": parts_map["Y"]})

    return {
        "gcode": gcode_str,
        "line_count": len(all_lines),
        "estimated_time_s": round(estimated_s, 1),
        "paths": paths,
    }
