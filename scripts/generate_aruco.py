"""
generate_aruco.py — A4 baskıya hazır ArUco kalibrasyon markerleri üretir.

Kullanım:
    python scripts/generate_aruco.py

Çıktı: output/aruco_print.pdf  (A4, doğrudan yazıcıdan bas)
       output/aruco_markers.png (yedek PNG)

Baskı talimatı:
    PDF'i aç → Yazdır → Ölçek: %100 / Gerçek Boyut / Actual Size
    → Her marker tam 40x40mm çıkar
"""

import os
import sys
import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

# Fiziksel boyutlar
DPI         = 300
MM_PER_INCH = 25.4
MARKER_MM   = 40          # marker iç boyutu (mm) — 40mm kolay kesim için
MARGIN_MM   = 15          # marker çevresinde boşluk
LABEL_MM    = 12          # etiket alanı yüksekliği

def mm2px(mm): return int(round(mm * DPI / MM_PER_INCH))

MARKER_PX = mm2px(MARKER_MM)
MARGIN_PX = mm2px(MARGIN_MM)
LABEL_PX  = mm2px(LABEL_MM)

# A4 piksel boyutu @ 300 DPI
A4_W_PX = mm2px(210)
A4_H_PX = mm2px(297)

FONT       = cv2.FONT_HERSHEY_SIMPLEX
ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

LABELS = [
    ("ID: 0", "Sol Ön  (X=10, Y=10)"),
    ("ID: 1", "Sağ Ön  (X=200, Y=10)"),
    ("ID: 2", "Sağ Arka (X=200, Y=200)"),
    ("ID: 3", "Sol Arka (X=10, Y=200)"),
]


def put_centered(img, text, cx, cy, scale=0.5, thick=1, color=0):
    (tw, th), _ = cv2.getTextSize(text, FONT, scale, thick)
    cv2.putText(img, text, (cx - tw//2, cy + th//2), FONT, scale, color, thick, cv2.LINE_AA)


def make_marker_cell(mid: int) -> np.ndarray:
    """Tek marker hücresi: marker + kesim çizgisi + etiket."""
    cell_w = MARKER_PX + MARGIN_PX * 2
    cell_h = MARKER_PX + MARGIN_PX * 2 + LABEL_PX
    cell = np.ones((cell_h, cell_w), np.uint8) * 255

    # Marker
    m = cv2.aruco.generateImageMarker(ARUCO_DICT, mid, MARKER_PX, borderBits=1)
    y0, x0 = MARGIN_PX, MARGIN_PX
    cell[y0:y0+MARKER_PX, x0:x0+MARKER_PX] = m

    # Kesim çizgisi (kesik)
    dash = 8
    for x in range(x0, x0+MARKER_PX, dash*2):
        cell[y0-2, x:x+dash] = 0
        cell[y0+MARKER_PX+1, x:x+dash] = 0
    for y in range(y0, y0+MARKER_PX, dash*2):
        cell[y:y+dash, x0-2] = 0
        cell[y:y+dash, x0+MARKER_PX+1] = 0

    # Köşe + işaretleri
    for (cy, cx) in [(y0, x0), (y0, x0+MARKER_PX),
                     (y0+MARKER_PX, x0), (y0+MARKER_PX, x0+MARKER_PX)]:
        cv2.line(cell, (cx-12, cy), (cx+12, cy), 0, 1)
        cv2.line(cell, (cx, cy-12), (cx, cy+12), 0, 1)

    # Etiket
    cx = cell_w // 2
    ly = MARGIN_PX + MARKER_PX + LABEL_PX // 3
    put_centered(cell, LABELS[mid][0], cx, ly,          scale=0.7, thick=2)
    put_centered(cell, LABELS[mid][1], cx, ly + mm2px(5), scale=0.4, color=80)

    return cell


def make_ruler(width_px: int, height_px: int = None) -> np.ndarray:
    """10mm aralıklı cetvel — baskıdan sonra ölçüp doğrulayabilirsiniz."""
    if height_px is None:
        height_px = mm2px(8)
    ruler = np.ones((height_px, width_px), np.uint8) * 255
    tick_10 = mm2px(10)
    tick_5  = mm2px(5)
    for px in range(0, width_px, tick_5):
        h = height_px // 2 if (px % tick_10 == 0) else height_px // 4
        cv2.line(ruler, (px, height_px), (px, height_px - h), 0, 1)
    for i, px in enumerate(range(0, width_px, tick_10)):
        put_centered(ruler, f"{i*10}", px, height_px//4, scale=0.3)
    put_centered(ruler, "mm", width_px - mm2px(8), height_px//2, scale=0.3, color=120)
    return ruler


def make_diagram() -> np.ndarray:
    """Tabla yerleşim şeması — hangi köşeye hangi marker gidiyor."""
    size = mm2px(80)
    pad  = mm2px(10)
    img  = np.ones((size + pad*2, size + pad*2), np.uint8) * 255

    # Tabla dış çerçeve
    cv2.rectangle(img, (pad, pad), (pad+size, pad+size), 0, 2)

    # Köşe kutuları + ID
    corners = [
        (pad+8,      pad+size-30, "0\nSol Ön"),
        (pad+size-30, pad+size-30, "1\nSağ Ön"),
        (pad+size-30, pad+8,       "2\nSağ Arka"),
        (pad+8,      pad+8,       "3\nSol Arka"),
    ]
    for (cx, cy, lbl) in corners:
        cv2.rectangle(img, (cx, cy), (cx+22, cy+22), 0, 2)
        id_char = lbl[0]
        put_centered(img, id_char, cx+11, cy+11, scale=0.6, thick=2)

    # Ok işareti (Home = sol ön köşe = X0 Y0)
    cv2.arrowedLine(img, (pad, pad+size), (pad+mm2px(12), pad+size), 0, 1, tipLength=0.3)
    cv2.arrowedLine(img, (pad, pad+size), (pad, pad+size-mm2px(12)), 0, 1, tipLength=0.3)
    put_centered(img, "X+", pad+mm2px(16), pad+size+5, scale=0.35)
    put_centered(img, "Y+", pad-8, pad+size-mm2px(16), scale=0.35)

    put_centered(img, "TABLA YERLESIM SEMASI", pad+size//2, pad-12, scale=0.4, thick=1)
    return img


def build_a4_sheet() -> np.ndarray:
    """4 markeri A4 sayfasına yerleştir."""
    sheet = np.ones((A4_H_PX, A4_W_PX), np.uint8) * 255

    cells = [make_marker_cell(i) for i in range(4)]
    ch, cw = cells[0].shape

    # 2x2 grid — ortala
    total_w = cw * 2 + mm2px(10)
    total_h = ch * 2 + mm2px(10)
    x_start = (A4_W_PX - total_w) // 2
    y_start = mm2px(25)  # üstten 25mm boşluk

    for idx, cell in enumerate(cells):
        row, col = divmod(idx, 2)
        x = x_start + col * (cw + mm2px(10))
        y = y_start + row * (ch + mm2px(10))
        sheet[y:y+ch, x:x+cw] = cell

    # Cetvel
    ruler_y = y_start + total_h + mm2px(8)
    ruler = make_ruler(total_w)
    rh = ruler.shape[0]
    sheet[ruler_y:ruler_y+rh, x_start:x_start+total_w] = ruler

    # Yerleşim şeması
    diag = make_diagram()
    dh, dw = diag.shape
    diag_x = (A4_W_PX - dw) // 2
    diag_y = ruler_y + rh + mm2px(8)
    if diag_y + dh < A4_H_PX:
        sheet[diag_y:diag_y+dh, diag_x:diag_x+dw] = diag

    # Başlık
    put_centered(sheet, "3D YAZICI KAPLAMA SISTEMI - ARUCO KALIBRASYON MARKERLARI",
                 A4_W_PX//2, mm2px(10), scale=0.55, thick=1)
    put_centered(sheet, f"Her marker {MARKER_MM}x{MARKER_MM}mm | Kesik cizgiden kes | Tablaya ID'e gore yapistir",
                 A4_W_PX//2, mm2px(17), scale=0.38, color=100)

    # Baskı talimatı (alt)
    put_centered(sheet, "BASKI: Dosyayi ac → Yazdir → Olcek %100 / Gercek Boyut sec",
                 A4_W_PX//2, A4_H_PX - mm2px(8), scale=0.4, thick=1, color=60)

    return sheet


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Markerlar üretiliyor…")
    sheet = build_a4_sheet()

    # PNG (DPI metadata gömülü — Preview otomatik boyutu bilir)
    png_path = os.path.join(OUTPUT_DIR, "aruco_markers.png")
    pil_img = Image.fromarray(sheet)
    pil_img.save(png_path, dpi=(DPI, DPI))
    print(f"✓ PNG kaydedildi: {png_path}")

    # PDF (en güvenilir baskı yöntemi)
    pdf_path = os.path.join(OUTPUT_DIR, "aruco_print.pdf")
    try:
        pil_img.save(pdf_path, "PDF", resolution=DPI)
        print(f"✓ PDF kaydedildi: {pdf_path}")
    except Exception as e:
        print(f"  PDF kaydedilemedi ({e}) — PNG kullan")

    # Bireysel marker PNG'leri
    for i in range(4):
        m = cv2.aruco.generateImageMarker(ARUCO_DICT, i, MARKER_PX, borderBits=1)
        p = os.path.join(OUTPUT_DIR, f"aruco_marker_{i}.png")
        Image.fromarray(m).save(p, dpi=(DPI, DPI))

    print()
    print("─" * 50)
    print("BASKI TALİMATI:")
    print("  1. output/aruco_print.pdf dosyasını aç")
    print("  2. Yazdır (Cmd+P)")
    print("  3. Ölçek → %100 / 'Gerçek Boyut' / 'Actual Size' seç")
    print("     (macOS Preview'da: Ölçek kutusuna 100 yaz)")
    print("  4. A4 kağıda bas")
    print(f"  5. Cetvelle ölç: marker tam {MARKER_MM}mm × {MARKER_MM}mm olmalı")
    print("  6. Kesik çizgilerden kes, tablaya yapıştır")
    print("─" * 50)


if __name__ == "__main__":
    main()
