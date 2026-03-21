"""
generate_aruco.py — Print-ready ArUco calibration markers.

Generates a PNG sheet with 4 ArUco markers (IDs 0–3, DICT_4X4_50) plus a
placement diagram showing where each marker goes on the printer bed.

Usage:
    python scripts/generate_aruco.py          # saves output/aruco_markers.png
    python scripts/generate_aruco.py --png    # also saves individual marker PNGs
"""

import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Constants ────────────────────────────────────────────────────────────────
MARKER_SIZE_PX = 300       # inner marker image size (pixels)
DPI = 300                  # target print DPI
MARKER_MM = 30             # desired physical marker size (mm)
MARGIN_PX = 60             # white margin around each marker
FONT = cv2.FONT_HERSHEY_SIMPLEX
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

LABELS = [
    ("0", "Sol Ön"),
    ("1", "Sağ Ön"),
    ("2", "Sağ Arka"),
    ("3", "Sol Arka"),
]

# Bed corner order for the diagram (mirrors the label positions)
DIAGRAM_CORNERS = [
    ("0\nSol Ön",   0, 0),    # top-left
    ("1\nSağ Ön",   0, 1),    # top-right
    ("2\nSağ Arka", 1, 1),    # bottom-right
    ("3\nSol Arka", 1, 0),    # bottom-left
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_marker_image(marker_id: int) -> np.ndarray:
    """Generate a single ArUco marker as a grayscale image."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    return cv2.aruco.generateImageMarker(aruco_dict, marker_id, MARKER_SIZE_PX, borderBits=1)


def draw_crosshair(img: np.ndarray, cx: int, cy: int, size: int = 15, color=0) -> None:
    """Draw a registration crosshair (used for corner marks)."""
    cv2.line(img, (cx - size, cy), (cx + size, cy), color, 1)
    cv2.line(img, (cx, cy - size), (cx, cy + size), color, 1)


def put_text_centered(img, text, cx, cy, scale=0.6, thickness=1, color=0):
    (w, h), _ = cv2.getTextSize(text, FONT, scale, thickness)
    cv2.putText(img, text, (cx - w // 2, cy + h // 2), FONT, scale, color, thickness, cv2.LINE_AA)


def build_marker_cell(marker_id: int, label: str, sublabel: str) -> np.ndarray:
    """Build a single cell: marker + cut border + text label."""
    cell_size = MARKER_SIZE_PX + MARGIN_PX * 2
    label_area = 60
    cell = np.ones((cell_size + label_area, cell_size), dtype=np.uint8) * 255

    # Place marker
    y0, x0 = MARGIN_PX, MARGIN_PX
    marker = make_marker_image(marker_id)
    cell[y0: y0 + MARKER_SIZE_PX, x0: x0 + MARKER_SIZE_PX] = marker

    # Dashed cut border around marker
    for x in range(x0, x0 + MARKER_SIZE_PX, 6):
        cell[y0 - 1, x] = 0
        cell[y0 + MARKER_SIZE_PX, x] = 0
    for y in range(y0, y0 + MARKER_SIZE_PX, 6):
        cell[y, x0 - 1] = 0
        cell[y, x0 + MARKER_SIZE_PX] = 0

    # Corner crosshairs
    for (cy, cx) in [(y0, x0), (y0, x0 + MARKER_SIZE_PX),
                     (y0 + MARKER_SIZE_PX, x0), (y0 + MARKER_SIZE_PX, x0 + MARKER_SIZE_PX)]:
        draw_crosshair(cell, cx, cy)

    # Label
    center_x = cell_size // 2
    put_text_centered(cell, f"ID: {label} — {sublabel}", center_x, cell_size + 20, scale=0.65, thickness=1)
    put_text_centered(cell, f"({MARKER_MM}x{MARKER_MM} mm @ {DPI} DPI)", center_x, cell_size + 44, scale=0.45, thickness=1, color=100)

    return cell


def build_diagram(bed_w_mm=220, bed_h_mm=220, size_px=600) -> np.ndarray:
    """Build a top-down printer bed placement diagram."""
    pad = 80
    img = np.ones((size_px + pad * 2, size_px + pad * 2), dtype=np.uint8) * 255

    # Bed outline
    cv2.rectangle(img, (pad, pad), (pad + size_px, pad + size_px), 0, 2)

    # Nozzle home marker (front-left = 0,0)
    cv2.circle(img, (pad, pad + size_px), 8, 0, -1)
    put_text_centered(img, "Home", pad + 5, pad + size_px - 14, scale=0.4)

    # Axes
    cv2.arrowedLine(img, (pad, pad + size_px), (pad + 70, pad + size_px), 0, 1, tipLength=0.3)
    cv2.arrowedLine(img, (pad, pad + size_px), (pad, pad + size_px - 70), 0, 1, tipLength=0.3)
    put_text_centered(img, "X+", pad + 80, pad + size_px + 18, scale=0.4)
    put_text_centered(img, "Y+", pad - 18, pad + size_px - 80, scale=0.4)

    # Bed size label
    put_text_centered(img, f"{bed_w_mm}mm", pad + size_px // 2, pad + size_px + 28, scale=0.5)
    put_text_centered(img, f"{bed_h_mm}mm", pad - 36, pad + size_px // 2, scale=0.5)

    # Marker positions — corners of the bed
    marker_offsets = {
        "0\nSol On":   (pad + 30, pad + size_px - 30),
        "1\nSag On":   (pad + size_px - 30, pad + size_px - 30),
        "2\nSag Arka": (pad + size_px - 30, pad + 30),
        "3\nSol Arka": (pad + 30, pad + 30),
    }
    for lbl, (cx, cy) in marker_offsets.items():
        cv2.rectangle(img, (cx - 20, cy - 20), (cx + 20, cy + 20), 0, 2)
        id_char = lbl[0]
        put_text_centered(img, id_char, cx, cy, scale=0.7, thickness=2)
        name = lbl.split("\n")[1]
        put_text_centered(img, name, cx, cy + 34, scale=0.38)

    # Title
    put_text_centered(img, "TABLA MARKER YERLESIM DIAGRAMI", pad + size_px // 2, 30, scale=0.55, thickness=1)
    put_text_centered(img, "Kamera tepeden bakiyor — marker'lari koseye yapi stir", pad + size_px // 2, 54, scale=0.38)

    return img


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--png", action="store_true", help="Also save individual marker PNGs")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Build 4 marker cells
    cells = [build_marker_cell(i, LABELS[i][0], LABELS[i][1]) for i in range(4)]

    # Find max cell dimensions and pad all cells to same size
    max_h = max(c.shape[0] for c in cells)
    max_w = max(c.shape[1] for c in cells)
    padded = []
    for c in cells:
        ph = max_h - c.shape[0]
        pw = max_w - c.shape[1]
        padded.append(np.pad(c, ((0, ph), (0, pw)), constant_values=255))

    # Arrange in 2×2 grid
    row0 = np.hstack([padded[0], np.ones((max_h, 20), dtype=np.uint8) * 255, padded[1]])
    row1 = np.hstack([padded[2], np.ones((max_h, 20), dtype=np.uint8) * 255, padded[3]])
    grid = np.vstack([row0, np.ones((20, row0.shape[1]), dtype=np.uint8) * 255, row1])

    # Build placement diagram
    diagram = build_diagram()
    # Pad diagram to same width as grid
    if diagram.shape[1] < grid.shape[1]:
        pw = grid.shape[1] - diagram.shape[1]
        diagram = np.pad(diagram, ((0, 0), (pw // 2, pw - pw // 2)), constant_values=255)
    elif diagram.shape[1] > grid.shape[1]:
        pw = diagram.shape[1] - grid.shape[1]
        grid = np.pad(grid, ((0, 0), (pw // 2, pw - pw // 2)), constant_values=255)

    # Header
    header_h = 80
    header = np.ones((header_h, grid.shape[1]), dtype=np.uint8) * 255
    put_text_centered(header, "3D YAZICI KAPLAMA SISTEMI — ARUCO KALIBRASYON MARKERLARI",
                      grid.shape[1] // 2, 28, scale=0.6, thickness=1)
    put_text_centered(header, f"300 DPI'da yazdir  |  Her marker {MARKER_MM}x{MARKER_MM} mm  |  Kesip tablanin koselerine yapistir",
                      grid.shape[1] // 2, 56, scale=0.42, color=80)

    separator = np.ones((30, grid.shape[1]), dtype=np.uint8) * 220

    sheet = np.vstack([header, separator, grid, separator, diagram])

    # Save main sheet
    out_path = os.path.join(OUTPUT_DIR, "aruco_markers.png")
    cv2.imwrite(out_path, sheet)
    print(f"✓ Saved: {out_path}")
    print(f"  → 300 DPI'da yazdir, marker boyutu otomatik {MARKER_MM}x{MARKER_MM}mm olur")

    # Save individual marker PNGs
    if args.png:
        for i in range(4):
            marker_img = make_marker_image(i)
            p = os.path.join(OUTPUT_DIR, f"aruco_marker_{i}.png")
            cv2.imwrite(p, marker_img)
            print(f"✓ Saved: {p}")

    print()
    print("Yapilacaklar:")
    print("  1. output/aruco_markers.png dosyasini yazdir (300 DPI)")
    print("  2. 4 markeri kes")
    print("  3. Yazicinin 4 kosesine yapistir (ID'lere gore)")
    print("  4. Her markerin merkez koordinatini olc (mm) → Ayarlar sayfasina gir")
    print("  5. Ayarlar → Kalibre Et butonuna bas")


if __name__ == "__main__":
    main()
