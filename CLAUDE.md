# CLAUDE.md — 3D Printer-Based Intelligent Coating System

## What This Project Does

Bu proje, Yıldız Teknik Üniversitesi Makine Mühendisliği bölümü bitirme projesidir.
Proje öğrencileri: Mehmet Ali Yesirci (22065077) ve Eren Alevli (22065618).
Danışman: Doç. Dr. Aslı GÜNAY BULUTSUZ.

### Fiziksel Sistem

Bir FDM 3D yazıcının (Ender 3 tipi) orijinal plastik baskı nozzle'ı tamamen sökülmüştür.
Yerine, bir şırınga pompası sistemi entegre edilmiştir. Bu şırınga pompası, NEMA 17 step
motor + lead screw ile 60mL'lik bir şırıngayı iterek, içindeki sıvıyı teflon tüp
aracılığıyla yazıcının nozzle pozisyonuna monte edilmiş özel bir uç'a basınçla iletir.

Şırınganın içindeki sıvı, **CuSO₄ (bakır sülfat) + stearic acid** bazlı bir kaplama
çözeltisidir. Bu çözelti, etanol bazlı bir solvent içinde çözünmüş halde tutulur.

Sistem, plastik veya metal parçaların düz yüzeylerinin üzerine bu çözeltiyi kontrollü
bir şekilde uygular. Kaplama sonrası termal işlem ile (100-700°C aralığında kademeli
ısıtma) stearic acid yanar ve CuSO₄, iletken bir CuO (bakır oksit) tabakasına dönüşür.

### Mevcut Durum (Çalışan Kısımlar)

- 3D yazıcı fiziksel olarak modifiye edilmiş durumda, şırınga pompası monte
- Nozzle yerine özel tasarlanmış uç takılı (3 farklı nozzle prototipi test edildi)
- Arduino Uno ile pompa step motoru sürülüyor
- BLTouch sensörü yazıcıda mevcut ve çalışıyor (Z-axis referanslama için)
- Marlin firmware çalışıyor, G-code komutlarını kabul ediyor
- Slicer'dan (Cura vb.) manuel olarak G-code üretilip yazıcıya yüklenebiliyor
- Parçalar tablaya çift taraflı bant ile sabitleniyor

### Eksik Olan ve Bu Yazılımın Çözeceği Problem

Şu anda her kaplama işlemi için:
1. Parçayı tablaya koymak
2. CAD'de kaplama pattern'ı çizmek
3. Slicer'da slice etmek
4. G-code'u SD kart veya USB ile yazıcıya yüklemek
5. Parçanın tam olarak tablada nerede olduğunu elle ayarlamak (nozzle'ı gözle hizalamak)

...gerekiyor. Bu hem yavaş hem de her parça değiştiğinde baştan yapılması lazım.

**Bu yazılım sistemi şunları otomatikleştirecek:**

1. **Kamera ile parçanın tablada nerede olduğunu tespit etme** — USB kamera tepeden
   bakıyor, OpenCV + ML modeli ile parçanın konturunu ve konumunu buluyor
2. **Piksel koordinatlarını yazıcı koordinatlarına dönüştürme** — ArUco marker bazlı
   kalibrasyon ile kamera pikseli → yazıcı mm'sine dönüşüm
3. **Otomatik G-code üretimi** — Tespit edilen kontura göre kaplama yolunu (zigzag,
   spiral vb.) otomatik hesaplama, slicer'a gerek kalmadan
4. **ML ile parça tanıma** — Farklı parçaları sınıflandırma, parça tipine göre
   varsayılan kaplama parametrelerini otomatik seçme
5. **React UI ile kullanıcı kontrolü** — Pompa hızı, kaplama parametreleri, canlı
   kamera görüntüsü, G-code önizleme, parça kütüphanesi yönetimi
6. **Tek tuşla kaplama** — "Tara → Önizle → Başlat" akışı ile tüm sürecin otomasyonu

### Neden ML Gerekli (Akademik Motivasyon)

Bu bir bitirme projesi ve transkriptte "yapay zeka / makine öğrenmesi" geçmesi
akademik açıdan önemli. ML şu noktalarda gerçek katma değer sağlıyor:

- **Parça segmentasyonu**: Benzer renkteki arka planlarda klasik thresholding
  başarısız olurken, eğitilmiş bir model çok daha güvenilir çalışır
- **Parça sınıflandırma**: "Bu parça daha önce işlenmiş X tipi parça" → otomatik
  parametre seçimi (pompa hızı, çizgi aralığı, feed rate)
- **Yön/rotasyon tespiti**: Parça tablaya farklı açılarda konabilir, model bunu algılar

Model: YOLOv8n (nano) — hafif, PC'de real-time çalışır, transfer learning ile
kullanıcının yüklediği parça fotoğraflarıyla eğitilebilir.

---

## System Architecture

### Donanım Bağlantı Şeması

```
                    ┌──────────────┐
                    │  USB Kamera  │
                    │ (tabla üstü) │
                    └──────┬───────┘
                           │ USB
                    ┌──────▼───────┐
  Serial (USB) ────┤              ├──── Serial (USB)
  ┌──────────┐     │     PC       │     ┌───────────────┐
  │ Arduino  │◄────┤  (Python +   ├────►│  3D Yazıcı    │
  │   Uno    │     │  FastAPI +   │     │  (Marlin USB) │
  │ (Pompa)  │     │   React)     │     │  + BLTouch    │
  └──────────┘     └──────────────┘     └───────────────┘
```

PC'ye 3 USB bağlantısı:
1. USB Kamera → OpenCV ile görüntü
2. Arduino Uno → Pompa kontrolü (serial, genelde /dev/ttyACM0 veya COM3)
3. 3D Yazıcı → G-code gönderme (serial, genelde /dev/ttyUSB0 veya COM4)

### Yazılım Stack

- **Backend**: Python 3.10+, FastAPI, OpenCV, Shapely, PySerial, ultralytics (YOLOv8)
- **Frontend**: React (Vite), Tailwind CSS, Axios
- **Arduino**: C++ firmware (basit serial komut protokolü)
- **Tüm sistem tek bir PC üzerinde çalışır**

---

## Directory Structure

```
coating-system/
├── backend/
│   ├── main.py                 # FastAPI entry, CORS, router includes
│   ├── config.py               # Serial portlar, baudrate, kamera index, vs
│   ├── routers/
│   │   ├── camera.py           # GET /camera/stream (MJPEG), POST /camera/capture
│   │   ├── detection.py        # POST /detect (parça tespit + sınıflandır)
│   │   ├── gcode.py            # POST /gcode/generate, POST /gcode/send
│   │   ├── pump.py             # POST /pump/start, /pump/stop, /pump/speed
│   │   └── parts.py            # CRUD parça kütüphanesi + fotoğraf upload
│   ├── services/
│   │   ├── camera_service.py   # Kamera capture, ArUco detection
│   │   ├── calibration.py      # Homography matrix hesaplama + kaydetme
│   │   ├── detection.py        # OpenCV kontur + ML inference
│   │   ├── gcode_generator.py  # Kontur→G-code (zigzag/spiral fill + polygon clipping)
│   │   ├── printer_serial.py   # Marlin G-code serial gönderimi (satır satır, ok bekle)
│   │   └── pump_serial.py      # Arduino pompa serial iletişimi
│   ├── ml/
│   │   ├── model.py            # YOLOv8 model load + predict
│   │   ├── train.py            # Model eğitim (transfer learning)
│   │   └── models/             # .pt model dosyaları
│   └── data/
│       ├── calibration.json    # Homography matrix + marker pozisyonları
│       ├── parts_db.json       # Parça kütüphanesi verisi
│       └── uploads/            # Yüklenen parça fotoğrafları
│
├── frontend/                   # React + Vite
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx       # Ana ekran: kamera + kontrol + önizleme
│   │   │   ├── PartsLibrary.jsx    # Parça kütüphanesi yönetimi
│   │   │   └── Settings.jsx        # Port ayarları, kalibrasyon tetikleme
│   │   └── components/
│   │       ├── CameraFeed.jsx      # MJPEG stream + kontur overlay
│   │       ├── GCodePreview.jsx    # Canvas üzerinde G-code yol çizimi
│   │       ├── PumpControls.jsx    # Pompa hız slider + start/stop
│   │       ├── CoatingParams.jsx   # Zigzag spacing, Z-offset, feed rate formu
│   │       └── PartUploader.jsx    # Drag-drop fotoğraf yükleme
│   └── package.json
│
├── arduino/
│   └── pump_controller/
│       └── pump_controller.ino     # Arduino pompa firmware
│
├── scripts/
│   ├── generate_aruco.py           # ArUco kalibrasyon marker PDF üretici
│   └── test_serial.py              # Serial bağlantı testi
│
├── requirements.txt
├── CLAUDE.md                       # Bu dosya
└── README.md
```

---

## Coding Standards & Rules

- Python: Type hints kullan, docstring yaz, PEP 8
- React: Functional components + hooks only, Tailwind utility classes
- Tüm API endpoint'leri RESTful, JSON response
- Serial iletişim thread-based olmalı (main thread'i bloklamamalı)
- Hata yönetimi: Serial bağlantı kopması, kamera bulunamazsa, marker görünmezse → graceful handle
- Config: Tüm port/baudrate/kamera ayarları `config.py`'den okunmalı, hardcoded OLMAMALI
- Kod ve yorumlar İngilizce, UI metinleri Türkçe olabilir
- Bu bir üniversite bitirme projesi → kod temiz, yorumlu, anlaşılır olmalı

---

## Critical Implementation Details

### 1. Kamera Kalibrasyon (En Önemli Adım)

Bu tüm sistemin temelidir. Kamera pikselinden yazıcı mm koordinatına dönüşüm
olmadan hiçbir şey çalışmaz.

**Konsept:**
Tablaya yapıştırılmış 4 ArUco marker var. Her marker'ın:
- Piksel koordinatı: Kamera görüntüsünden tespit edilir
- Gerçek koordinatı: Yazıcı koordinat sisteminde elle ölçülmüş (mm cinsinden)

Bu 4 nokta çifti ile `cv2.findHomography()` çağrılır → 3x3 homografi matrisi (H) elde edilir.
H matrisi, kameradaki herhangi bir pikseli yazıcı mm koordinatına dönüştürür.

```python
# ArUco: DICT_4X4_50, marker boyutu 30x30mm
# Kalibrasyon akışı:
# 1. Kameradan frame al
# 2. cv2.aruco.ArucoDetector ile 4 marker'ı bul
# 3. Her marker'ın piksel merkez koordinatını al (4 köşenin ortalaması)
# 4. config.py'deki gerçek mm koordinatlarıyla eşle
# 5. cv2.findHomography(pixel_pts, real_pts) → H matrisi
# 6. H'yi calibration.json'a kaydet

# Dönüşüm fonksiyonu:
def pixel_to_mm(px, py, H):
    pt = np.array([px, py, 1.0])
    result = H @ pt
    return result[0]/result[2], result[1]/result[2]
```

**config.py'de marker pozisyonları:**
```python
ARUCO_MARKER_POSITIONS_MM = {
    0: (10.0, 10.0),    # sol ön
    1: (210.0, 10.0),   # sağ ön
    2: (210.0, 210.0),  # sağ arka
    3: (10.0, 210.0),   # sol arka
}
```
Bu değerler kullanıcı tarafından Settings sayfasından değiştirilebilmeli.

### 2. Parça Tespit Pipeline

```
Kameradan frame al
    → GaussianBlur(frame, (5,5), 0)                    # gürültü azaltma
    → cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)           # gri tonlama
    → cv2.adaptiveThreshold(...)                         # eşikleme
    → cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)  # boşluk kapatma
    → cv2.findContours(...)                              # kontur bulma
    → En büyük konturu seç (area filtre: min 1000px²)    # = parça
    → cv2.approxPolyDP ile konturu sadeleştir             # nokta sayısını azalt
    → Her kontur noktasını pixel_to_mm() ile dönüştür     # piksel → mm
    → (Opsiyonel) YOLOv8 model ile parça sınıfını belirle
```

**Fallback stratejisi:** ML model yoksa veya confidence < 0.5 ise → pure OpenCV pipeline.
Sistem ML olmadan da temel düzeyde çalışabilmeli.

### 3. G-code Üretimi (Kaplama Yolu)

Bu modül, tespit edilen parça konturunu (mm koordinatlarında) alır ve
yazıcının takip edeceği kaplama yolunu G-code olarak üretir.

**Parametreler (kullanıcı tarafından UI'dan ayarlanabilir):**
- `line_spacing`: mm — zigzag çizgiler arası mesafe (varsayılan: 1.0mm)
- `z_offset`: mm — nozzle-yüzey mesafesi (varsayılan: 0.3mm)
- `feed_rate`: mm/min — kaplama hareketi hızı (varsayılan: 600)
- `travel_rate`: mm/min — boş hareket hızı (varsayılan: 1500)
- `band_thickness`: mm — çift taraflı bant kalınlığı (varsayılan: 1.0mm)
- `pattern_type`: "zigzag" | "spiral" | "parallel" (varsayılan: zigzag)

### 4. Serial İletişim Protokolü

**Marlin (3D Yazıcı):**
- Baudrate: 115200
- G-code satır satır gönderilir
- Her satırdan sonra "ok\n" yanıtını bekle
- Timeout: 30 saniye (G28 ve G29 uzun sürebilir)
- Bağlantı açıldığında Marlin boot mesajı gelir, bunu bekle/atla

**Arduino (Pompa):**
- Baudrate: 9600
- Komutlar: `START\n`, `STOP\n`, `SPEED:XXX\n`, `STATUS\n`
- Yanıtlar: `OK\n`, `ERROR:message\n`, `STATUS:running:150\n`

### 5. ML Model Detayları

- **Base model**: YOLOv8n (nano) — en hafif versiyon, PC'de real-time
- **Task**: Object detection + classification
- **Transfer learning**: Kullanıcı fotoğraf yükler → etiketler → `POST /parts/retrain`
- **Fallback**: Model yoksa VEYA confidence < 0.5 → pure OpenCV kontur tespiti kullan
- **Model dosyası**: `backend/ml/models/parts_model.pt`

---

## API Endpoints

```
# Kamera
GET  /camera/stream              → MJPEG video stream
POST /camera/capture             → Tek frame al → {image: base64, timestamp}
POST /camera/calibrate           → ArUco kalibrasyon yap → {success, matrix, error}

# Tespit
POST /detect                     → Parça tespit → {contour_mm, class_name, confidence, bbox}
POST /detect/preview             → Tespit + overlay görüntü → {image: base64 (annotated)}

# G-code
POST /gcode/generate             → {contour_mm, params} → {gcode, line_count, estimated_time}
POST /gcode/preview              → {gcode} → {paths: [{x,y}[], ...]}
POST /gcode/send                 → G-code'u yazıcıya gönder (async) → {job_id}
GET  /gcode/status               → {status, current_line, total_lines, elapsed_time}
POST /gcode/stop                 → Durdur (M112)

# Pompa
POST /pump/start                 → {rpm} → Pompayı başlat
POST /pump/stop                  → Pompayı durdur
POST /pump/speed                 → {rpm} → Hız değiştir
GET  /pump/status                → {running, rpm}

# Parça Kütüphanesi
GET    /parts                    → Tüm parçalar
POST   /parts                    → Yeni parça (multipart)
PUT    /parts/{id}               → Güncelle
DELETE /parts/{id}               → Sil
POST   /parts/retrain            → ML retrain (async)
GET    /parts/retrain/status     → Eğitim durumu

# Sistem
GET  /system/ports               → Serial portlar
GET  /system/status              → Bağlantı durumları
POST /system/config              → Config güncelle
```

---

## Build & Run

```bash
# Backend
cd backend
pip install -r ../requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend
npm install
npm run dev   # → http://localhost:5173

# ArUco marker üret (yazdır ve tablaya yapıştır)
python scripts/generate_aruco.py

# Serial bağlantı test
python scripts/test_serial.py --list
python scripts/test_serial.py --port /dev/ttyUSB0 --target printer
```

---

## Implementation Priority Order

1. **config.py + main.py** — Temel FastAPI app
2. **camera_service.py + camera router** — Kamera stream
3. **calibration.py** — ArUco + homografi
4. **detection.py (OpenCV only)** — Kontur tespiti
5. **gcode_generator.py** — Zigzag G-code
6. **printer_serial.py** — Marlin gönderimi
7. **pump_serial.py** — Arduino pompa
8. **Frontend: Dashboard** — Ana sayfa
9. **Frontend: GCodePreview** — Canvas önizleme
10. **ML model.py** — YOLOv8 entegrasyonu
11. **Frontend: PartsLibrary** — Parça yönetimi
12. **train.py** — Model retrain
13. **Frontend: Settings** — Ayarlar sayfası

---

## Important Notes

- Sıcaklık komutları (M104, M140) G-code'a EKLEME — ısıtıcı bağlı değil
- `opencv-contrib-python-headless` paketi ArUco için GEREKLİ
- Serial portlar: Linux: /dev/ttyUSB0, /dev/ttyACM0 — Windows: COM3, COM4
- Marlin'e bağlanınca 2 saniye bekle (boot)
- BLTouch probe: `G30 X... Y...` (tek nokta) veya `G29` (full mesh)
- MJPEG boundary: `--frame\r\nContent-Type: image/jpeg\r\n\r\n{jpeg_bytes}`
