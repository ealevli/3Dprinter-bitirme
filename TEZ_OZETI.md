# 3D Yazıcı Tabanlı Akıllı Kaplama Sistemi — Teknik Özet

**Proje**: Yıldız Teknik Üniversitesi, Makine Mühendisliği Bölümü, 2026 Bitirme Projesi  
**Öğrenciler**: Eren Alevli (22065618)  
**Danışman**: Doç. Dr. Aslı Günay Bulutsuz

---

## 1. Projenin Amacı ve Motivasyonu

Bu proje, geleneksel FDM (Fused Deposition Modeling) 3D yazıcı altyapısını yeniden
kullanarak akıllı, görüntü tabanlı bir yüzey kaplama sistemi geliştirmeyi amaçlamaktadır.

Standart plastik eritme nozulunun yerine **şırınga pompası** entegre edilmiş ve yazıcının
üç eksenli hareket sistemi, kaplama solüsyonunu parça yüzeyine hassas biçimde uygulamak
için kullanılmıştır.

Sistemin akademik katkısı şu üç noktada yoğunlaşmaktadır:

1. **Görüntü işleme ile konum tespiti** — Tablaya yerleştirilen parçanın koordinatları
   kamera aracılığıyla otomatik olarak belirlenmektedir.
2. **Otomatik G-code üretimi** — Tespit edilen parça konturu, slicer yazılımına gerek
   duyulmaksızın doğrudan kaplama yoluna dönüştürülmektedir.
3. **Makine öğrenmesi ile parça sınıflandırma** — YOLOv8 tabanlı model sayesinde sistem
   farklı parça tiplerini tanıyabilmekte ve kaplama parametrelerini otomatik seçebilmektedir.

---

## 2. Fiziksel Sistem (Donanım)

### 2.1 Temel Platform

| Bileşen | Model / Özellik |
|---------|-----------------|
| 3D Yazıcı | Creality Ender 3 tipi FDM yazıcı |
| Yazıcı Firmware | Marlin (G-code tabanlı, USB serial haberleşme) |
| Tabla Boyutu | 220 × 220 mm |
| Konum Hassasiyeti | ±0,1 mm (step motor adım çözünürlüğü) |
| Z-ekseni referanslama | BLTouch otomatik seviye sensörü |

### 2.2 Şırınga Pompası Sistemi

Yazıcının orijinal ekstruder ve ısıtıcı bloğu tamamen sökülmüştür. Yerine montaj edilen
sistem şu bileşenlerden oluşmaktadır:

- **Şırınga**: 60 mL plastik tıbbi şırınga
- **Sürücü mekanizması**: NEMA 17 step motor + M5 kurşun vida (lead screw)
- **Motor sürücü kartı**: A4988 step motor sürücüsü
- **Mikrodenetleyici**: Arduino Uno (ATmega328P, FT232R USB-UART çipi)
- **İletim hattı**: PTFE (Teflon) tüp, şırıngadan nozzle pozisyonuna
- **Uç (nozzle)**: Üç farklı prototip test edilmiştir (iğne uç, düz uç, konik uç)

**Pompa haberleşme protokolü** (9600 baud, serial):

```
PC → Arduino  |  Arduino → PC
START         |  OK
STOP          |  OK
SPEED:N       |  OK          (N = 1–1000 adım/saniye)
STATUS        |  STATUS:running:150
```

### 2.3 Kaplama Solüsyonu

Solüsyon içeriği:
- **CuSO₄** (bakır(II) sülfat) — iletken tabaka kaynağı
- **Stearik asit** (C₁₈H₃₆O₂) — bağlayıcı / matris
- **Etanol** — çözücü (solvent)

Uygulama sonrası termal işlem süreci:

| Sıcaklık Aralığı | Süreç |
|------------------|-------|
| 20 → 100 °C | Etanol buharlaşması |
| 100 → 300 °C | Stearik asidin yanması |
| 300 → 700 °C | CuSO₄ → CuO dönüşümü (iletken tabaka oluşumu) |

### 2.4 Kalibrasyon Sistemi (ArUco Marker)

Kamera koordinat sistemi ile yazıcı koordinat sistemi arasındaki dönüşüm, ArUco marker
tabanlı homografi matrisi ile sağlanmaktadır.

- **Marker türü**: ArUco DICT_4X4_50
- **Marker boyutu**: 40 × 40 mm
- **Yerleşim**: Tablaya 4 köşeye sabitlenmiş
- **Dönüşüm yöntemi**: `cv2.findHomography()` ile 3×3 H matrisi
- **Formül**: `[X_mm, Y_mm]^T = H · [u_px, v_px, 1]^T`

3 marker görünür olduğunda affine transform ile fallback mekanizması devreye girmektedir.

---

## 3. Yazılım Mimarisi

### 3.1 Genel Yapı

```
┌──────────────────────────────────────────────────────┐
│                    Kullanıcı (React UI)               │
│  Dashboard | Parça Kütüphanesi | Ayarlar | Nasıl K.  │
└──────────────────────┬───────────────────────────────┘
                       │ HTTP/REST (port 5173 → 8000)
┌──────────────────────▼───────────────────────────────┐
│                 FastAPI Backend (Python)               │
│  /camera  /detect  /gcode  /pump  /parts  /system    │
└────┬──────────┬──────────────────────────────────────┘
     │ USB       │ USB
┌────▼───┐  ┌───▼──────────────────┐
│Arduino │  │ 3D Yazıcı (Marlin)   │
│ Pompa  │  │ G-code serial stream  │
└────────┘  └──────────────────────┘
```

### 3.2 Backend Servisleri

| Servis | Dosya | Görev |
|--------|-------|-------|
| Kamera | `camera_service.py` | Frame yakalama, arka plan thread'i |
| Kalibrasyon | `calibration.py` | ArUco tespiti, homografi hesaplama |
| Tespit | `detection.py` | İki aşamalı parça kontur tespiti |
| G-code Üretici | `gcode_generator.py` | Kontur → Kaplama yolu |
| Yazıcı Serial | `printer_serial.py` | Marlin G-code gönderimi |
| Pompa Serial | `pump_serial.py` | Arduino pompa kontrolü |
| ML Modeli | `ml/model.py` | YOLOv8 çıkarım |

### 3.3 Frontend Bileşenleri

| Bileşen | Açıklama |
|---------|----------|
| `Dashboard.jsx` | Ana ekran: kamera görüntüsü, tespit, G-code önizleme |
| `GCodePreview.jsx` | Canvas üzerinde kaplama yolu animasyonu |
| `CoatingParams.jsx` | Kaplama parametreleri (çizgi aralığı, Z-offset, hız) |
| `PumpControls.jsx` | Pompa hız kontrolü ve start/stop |
| `Settings.jsx` | Port ayarları, kalibrasyon, G-code sekansları |
| `PartsLibrary.jsx` | Parça veritabanı yönetimi |
| `HowToUse.jsx` | Kullanım kılavuzu |

---

## 4. Görüntü İşleme Pipeline'ı

### 4.1 Parça Tespit Akışı

```
Kamera frame'i al (OpenCV, USB kamera)
    ↓
GaussianBlur(5×5) — gürültü azaltma
    ↓
OTSU eşikleme — beyaz kağıdı bul
    ↓
En büyük parlak bölge → kağıt ROI (Region of Interest)
    ↓
ROI içinde OTSU eşikleme — koyu parçayı bul
    ↓
Morfolojik kapama (closing) — boşlukları doldur
    ↓
findContours — kontur noktaları
    ↓
approxPolyDP — kontur sadeleştirme
    ↓
pixel_to_mm(H) → yazıcı koordinatlarına dönüştür
```

**Fallback stratejisi**: Kağıt tespit edilemezse tek adımlı global thresholding kullanılır.

### 4.2 Kalibrasyon Akışı

```
Kameradan frame al
    ↓
cv2.aruco.ArucoDetector (DICT_4X4_50, gevşetilmiş parametreler)
    ↓
≥ 4 marker: findHomography (tam perspektif dönüşümü)
= 3 marker: getAffineTransform (affine fallback)
    ↓
H matrisi → data/calibration.json kaydedilir
```

---

## 5. G-code Üretim Algoritması

### 5.1 Kaplama Desenleri

Sistem üç farklı desen üretmektedir:

| Desen | Açıklama | Kullanım Senaryosu |
|-------|----------|-------------------|
| Zigzag | İleri-geri tarama çizgileri | Genel amaçlı, düzgün kaplama |
| Paralel | Tek yönlü tarama | Yön bağımlı kaplamalar |
| Spiral | İçe doğru çerçeveleme | Hassas kenarlı parçalar |

### 5.2 Üretim Adımları

```python
1. Shapely Polygon(kontur_mm) oluştur
2. WALL-OUTER: Perimeter boyunca tek geçiş (dış çevre çizgisi)
3. İnfill:
   y = y_min + band_thickness
   while y < y_max - band_thickness:
       scan_line = LineString([(x_min-1, y), (x_max+1, y)])
       kesişim = polygon.intersection(scan_line)
       zigzag: çift satırlarda x yönünü tersine çevir
       y += line_spacing
4. Placeholder'ları doldur: {part_x}, {part_y}, {z_coat}, vs.
5. G-code string döndür
```

### 5.3 G-code Yapısı

```gcode
; === Başlangıç Sekansı ===
G28 X Y           ; Home X ve Y
G1 Z6.300         ; Güvenli yükseklik
G1 X{part_x} Y{part_y} F1500   ; Parça başlangıcına git

; === WALL-OUTER (Dış Çevre) ===
G0 F1500 X... Y... Z6.300     ; Hareket
G1 F300 Z1.300                ; Kaplama yüksekliğine in
G1 F600 X... Y...             ; Dış çevre tara

; === İnfill (Dolgu) ===
; ... zigzag / parallel / spiral çizgiler ...

; === Bitiş Sekansı ===
G0 F300 Z16.300               ; Nozzle'ı yukarı kaldır
G0 F1500 X0 Y220              ; Park pozisyonu
M84 X Y E                     ; Motorları devre dışı bırak
```

### 5.4 Kaplama Parametreleri

| Parametre | Varsayılan | Aralık | Etki |
|-----------|------------|--------|------|
| Çizgi Aralığı | 1.0 mm | 0.1–5.0 mm | Kaplama yoğunluğu |
| Z-Offset | 0.3 mm | 0.1–2.0 mm | Nozzle-yüzey mesafesi |
| Feed Rate | 600 mm/dak | 100–3000 | Kaplama hareketi hızı |
| Travel Rate | 1500 mm/dak | 500–5000 | Boş hareket hızı |
| Bant Kalınlığı | 1.0 mm | 0.3–5.0 mm | Kenar boşluğu |
| Desen | zigzag | zigzag/paralel/spiral | Dolgu yöntemi |

---

## 6. Makine Öğrenmesi Entegrasyonu

### 6.1 Model Seçimi: YOLOv8n (Nano)

Modelin seçim gerekçeleri:

- **Hız**: YOLOv8n, CPU üzerinde ~15-30 ms/frame çıkarım süresi (real-time)
- **Boyut**: ~3.2 MB model dosyası, gömülü sistemlerde çalışabilir
- **Transfer learning**: Kullanıcının yüklediği fotoğraflarla ince ayar (fine-tuning) yapılabilir
- **Çoklu görev**: Tespit + sınıflandırma tek geçişte gerçekleşir

### 6.2 Kullanım Senaryoları

| Senaryo | OpenCV (fallback) | YOLOv8 (ML) |
|---------|------------------|-------------|
| Yüzey tespiti | ✓ | ✓ |
| Farklı renk arka plan | ✗ | ✓ |
| Parça sınıflandırma | ✗ | ✓ |
| Rotasyon tespiti | Kısıtlı | ✓ |
| Güven skoru | ✗ | ✓ |

### 6.3 Fallback Mekanizması

Model bulunamazsa veya güven skoru < 0.5 ise sistem otomatik olarak OpenCV tabanlı
kontur tespitine geçer. Bu sayede sistem, ML modeli olmadan da temel kaplama
işlemlerini gerçekleştirebilmektedir.

---

## 7. Haberleşme Protokolleri

### 7.1 Marlin (3D Yazıcı)

- **Baud rate**: 115200
- **Protokol**: Satır satır G-code gönderimi
- **Akış kontrolü**: Her satır sonrası `ok\n` yanıtı beklenir
- **Timeout**: 30 saniye (G28 ve G29 uzun sürebilir)
- **Bağlantı**: USB CDC Serial (Linux: `/dev/ttyUSB0`, Mac: `/dev/cu.*`, Windows: `COM#`)

### 7.2 Arduino Pompa

- **Baud rate**: 9600
- **Protokol**: Newline terminated ASCII komutları
- **Komutlar**: `START`, `STOP`, `SPEED:N`, `STATUS`
- **Thread safety**: `threading.Lock()` ile korunan gönderim/alma

### 7.3 REST API (Frontend ↔ Backend)

- **Framework**: FastAPI (Python), asenkron endpoint'ler
- **Format**: JSON request/response
- **CORS**: React geliştirme sunucusu (5173) için açık
- **Canlı akış**: MJPEG yerine frame-by-frame polling (`GET /camera/frame`)

---

## 8. Teknoloji Yığını (Tech Stack)

### Backend

| Kütüphane | Versiyon | Kullanım Amacı |
|-----------|----------|----------------|
| FastAPI | ≥0.109 | REST API framework |
| OpenCV (cv2) | ≥4.8 | Görüntü işleme |
| opencv-contrib-python-headless | ≥4.8 | ArUco marker desteği |
| NumPy | ≥1.24 | Matris işlemleri |
| Shapely | ≥2.0 | Polygon kırpma (infill) |
| PySerial | ≥3.5 | Serial haberleşme |
| Ultralytics | ≥8.0 | YOLOv8 model |
| Pillow | ≥10.0 | ArUco PDF üretimi |
| Uvicorn | ≥0.27 | ASGI sunucusu |

### Frontend

| Kütüphane | Versiyon | Kullanım Amacı |
|-----------|----------|----------------|
| React | 18 | UI framework |
| Vite | 5 | Build tool / dev server |
| Tailwind CSS | 3 | Utility-first CSS |
| Axios | ≥1.6 | HTTP istekleri |
| React Router | 6 | Sayfa yönlendirmesi |

### Arduino

| Bileşen | Açıklama |
|---------|----------|
| Arduino Uno (ATmega328P) | Mikrodenetleyici |
| A4988 Step Motor Sürücüsü | NEMA 17 kontrolü |
| Firmware dili | C++ (Arduino IDE) |

---

## 9. Sistem Çalışma Akışı (Uçtan Uca)

```
1. BAŞLAT
   ├── Backend: uvicorn main:app --port 8000
   └── Frontend: npm run dev → localhost:5173

2. KURULUM (bir kez)
   ├── ArUco kağıtlarını tablaya yapıştır
   ├── Ayarlar → Serial portları seç → Kaydet
   └── Ayarlar → Kalibre Et → "4/4 marker bulundu" ✓

3. KAPLAMA İŞLEMİ (her parça için)
   ├── Parçayı tablaya koy (çift taraflı bantla sabitle)
   ├── Dashboard → TARA
   │     ├── Kameradan frame al
   │     ├── Kağıt ROI bul → parça konturu tespit et
   │     ├── Piksel → mm dönüşümü (H matrisi)
   │     └── Tespit bilgisi göster (boyut, nokta sayısı, güven)
   ├── Dashboard → ÖNİZLE
   │     ├── Kontur + parametrelerle G-code üret
   │     ├── Canvas'ta kaplama yolunu göster
   │     └── Ham G-code'u göster / kopyala
   └── Dashboard → BAŞLAT
         ├── G-code'u Marlin'e satır satır gönder
         ├── Pompa START komutu → solüsyon akmaya başlar
         └── Yazıcı kaplama yolunu tamamlar

4. TERMAL İŞLEM (fırın)
   └── 100°C → 300°C → 700°C kademeli ısıtma
       → Etanol uçar → Stearik asit yanar → CuO tabaka oluşur
```

---

## 10. Gerçekleştirilen Test Sonuçları

| Test | Durum | Notlar |
|------|-------|--------|
| Kamera stream (USB) | ✅ | Frame-by-frame polling, stabil |
| ArUco kalibrasyon (4/4) | ✅ | Multi-preprocessing ile fisheye uyumlu |
| Parça tespiti (beyaz kağıt üzeri) | ✅ | İki aşamalı OTSU, güvenilir |
| Piksel→mm dönüşümü | ✅ | Homografi, <1 mm hata |
| G-code üretimi (zigzag) | ✅ | Shapely polygon clip, Cura tarzı |
| G-code üretimi (spiral) | ✅ | İçe doğru çerçeveleme |
| G-code önizleme (canvas) | ✅ | Duvar + dolgu ayrı renk |
| Arduino bağlantısı | ✅ | FT232R, /dev/cu.usbserial-A5069RR4 |
| Arduino firmware | 🔄 | Yükleme aşamasında |
| Marlin bağlantısı | ⏳ | 3D yazıcı henüz bağlanmadı |
| YOLOv8 ML modeli | ⏳ | Eğitim verisi toplanmadı |
| Uçtan uca kaplama | ⏳ | Donanım entegrasyonu devam ediyor |

---

## 11. Özgün Katkılar

Bu proje kapsamında geliştirilen özgün çözümler:

1. **İki aşamalı görüntü işleme**: Kağıt → parça hiyerarşik tespiti,
   benzer renkli zeminlerde klasik eşikleme başarısız olurken güvenilir sonuç üretiyor.

2. **Gerçek zamanlı homografi güncellemesi**: Her kaplama öncesinde marker konumları
   yeniden hesaplanarak parça yer değişikliği otomatik telafi ediliyor.

3. **Shapely tabanlı infill**: Polygon kırpma ile klasik slicer algoritmalarından
   bağımsız, parametrik G-code üretimi gerçekleştiriliyor.

4. **Düzenlenebilir G-code sekansları**: Kullanıcı, `{part_x}`, `{part_y}`, `{z_coat}`
   gibi placeholder'lar içeren başlangıç/bitiş sekanslarını UI'dan düzenleyebiliyor.

5. **Modüler fallback mimarisi**: ML modeli, kamera, serial bağlantı gibi her bileşen
   bağımsız olarak devre dışı bırakılabilmekte; sistem kısmi donanımla çalışmaya devam edebilmektedir.

---

## 12. Dizin Yapısı

```
coating-system/
├── backend/
│   ├── main.py                   # FastAPI uygulaması, CORS, router
│   ├── config.py                 # Tüm sabit değerler (port, baudrate, kamera)
│   ├── routers/                  # HTTP endpoint'leri
│   │   ├── camera.py             # /camera/frame, /camera/calibrate
│   │   ├── detection.py          # /detect
│   │   ├── gcode.py              # /gcode/generate, /gcode/send
│   │   ├── pump.py               # /pump/start, /pump/stop
│   │   └── parts.py              # /parts CRUD
│   ├── services/                 # İş mantığı
│   │   ├── camera_service.py
│   │   ├── calibration.py
│   │   ├── detection.py
│   │   ├── gcode_generator.py
│   │   ├── printer_serial.py
│   │   └── pump_serial.py
│   ├── ml/
│   │   ├── model.py              # YOLOv8 yükleme + çıkarım
│   │   └── train.py              # Transfer learning
│   └── data/
│       ├── calibration.json      # H matrisi
│       └── parts_db.json         # Parça veritabanı
├── frontend/
│   └── src/
│       ├── pages/                # Dashboard, Settings, PartsLibrary, HowToUse
│       └── components/           # GCodePreview, PumpControls, CoatingParams
├── arduino/
│   └── pump_controller/
│       └── pump_controller.ino   # NEMA17 step motor firmware
└── scripts/
    ├── generate_aruco.py         # ArUco PDF üretici
    ├── test_serial.py            # Serial bağlantı testi
    └── test_motor.py             # Arduino motor fonksiyon testi
```

---

*Bu belge sistem geliştirilmesi sürecinde yazılmıştır. Son güncellenme: Nisan 2025.*
