"""
generate_aruco.py — Print ArUco calibration markers.

Generates a PDF (or PNG images) with 4 ArUco markers (IDs 0–3) that should be
printed and glued to the printer bed at the positions defined in config.py.

Usage:
    python scripts/generate_aruco.py          # saves aruco_markers.pdf
    python scripts/generate_aruco.py --png    # saves individual PNG files
"""

import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MARKER_SIZE_PX = 200   # pixel resolution of each marker image
BORDER_BITS = 1


def generate_marker(marker_id: int) -> np.ndarray:
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, MARKER_SIZE_PX, borderBits=BORDER_BITS)
    return img


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--png", action="store_true", help="Save individual PNG files")
    args = parser.parse_args()

    markers = [generate_marker(i) for i in range(4)]
    labels = ["0: Sol Ön", "1: Sağ Ön", "2: Sağ Arka", "3: Sol Arka"]

    if args.png:
        for i, img in enumerate(markers):
            path = f"aruco_marker_{i}.png"
            cv2.imwrite(path, img)
            print(f"Saved {path}")
        return

    # Compose a simple 2×2 grid image.
    pad = 20
    cell = MARKER_SIZE_PX + pad * 2
    grid = np.ones((cell * 2, cell * 2), dtype=np.uint8) * 255

    positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
    for idx, (row, col) in enumerate(positions):
        y = row * cell + pad
        x = col * cell + pad
        grid[y: y + MARKER_SIZE_PX, x: x + MARKER_SIZE_PX] = markers[idx]

    out_path = "aruco_markers.png"
    cv2.imwrite(out_path, grid)
    print(f"Saved {out_path}  (print at 300 DPI for ~30mm marker size)")


if __name__ == "__main__":
    main()
