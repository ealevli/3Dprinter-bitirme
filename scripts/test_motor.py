#!/usr/bin/env python3
"""
test_motor.py — Arduino Pompa Motor Test Scripti
-------------------------------------------------
Bu script, Arduino firmware yüklendikten sonra motorun
doğru çalışıp çalışmadığını test eder.

Kullanım:
    python scripts/test_motor.py --port /dev/cu.usbserial-A5069RR4
    python scripts/test_motor.py --port COM4          # Windows
    python scripts/test_motor.py --auto               # Portu otomatik bul
"""

import argparse
import sys
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("HATA: pyserial kurulu değil. Çalıştır: pip install pyserial")
    sys.exit(1)


# ── ANSI renk kodları ──────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg):  print(f"  {RED}✗{RESET} {msg}")
def info(msg):  print(f"  {CYAN}→{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{RESET} {msg}")
def header(msg): print(f"\n{BOLD}{msg}{RESET}")


# ── Port bulma ─────────────────────────────────────────────────────────────────

def find_arduino_port():
    """Bağlı portları tara, Arduino/FT232/CH340 olan ilkini döndür."""
    ports = list(serial.tools.list_ports.comports())
    keywords = ["arduino", "ft232", "ch340", "ch34x", "usb serial", "uart", "usbserial"]
    for p in ports:
        desc = (p.description or "").lower()
        manu = (p.manufacturer or "").lower()
        if any(k in desc or k in manu for k in keywords):
            return p.device, p.description
    # Fallback: tüm portları listele
    return None, None


def list_ports():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        warn("Hiç serial port bulunamadı!")
    else:
        print("\nMevcut portlar:")
        for p in ports:
            print(f"  {p.device:30s}  {p.description}")


# ── Test fonksiyonları ─────────────────────────────────────────────────────────

def send_cmd(ser: serial.Serial, cmd: str, timeout: float = 3.0) -> str:
    """Komut gönder, cevabı oku."""
    ser.reset_input_buffer()
    ser.write((cmd.strip() + "\n").encode())
    ser.timeout = timeout
    resp = ser.readline().decode(errors="replace").strip()
    return resp


def run_tests(port: str, baudrate: int = 9600):
    header(f"Arduino Motor Testi — {port}")
    print(f"  Bağlanıyor ({baudrate} baud)...")

    try:
        ser = serial.Serial(port, baudrate, timeout=3)
    except serial.SerialException as e:
        fail(f"Port açılamadı: {e}")
        print("\n  Olası nedenler:")
        print("  - Port yanlış (--port argümanını kontrol et)")
        print("  - Arduino başka program tarafından kullanılıyor (Arduino IDE Serial Monitor?)")
        print("  - İzin hatası → 'sudo chmod 666 /dev/cu.usbserial-...' dene")
        return False

    info("Arduino boot bekleniyor (2 sn)...")
    time.sleep(2.0)

    # Boot mesajlarını temizle
    ser.reset_input_buffer()

    all_passed = True

    # ── Test 1: STATUS ──────────────────────────────────────────────────────
    header("Test 1: STATUS komutu")
    resp = send_cmd(ser, "STATUS")
    info(f"Cevap: '{resp}'")
    if "STATUS:" in resp:
        ok("STATUS komutu çalışıyor")
    else:
        fail(f"Beklenen: 'STATUS:stopped:0'  Gelen: '{resp}'")
        fail("Firmware yüklü değil veya yanlış firmware yüklü!")
        ser.close()
        return False

    # ── Test 2: SPEED ───────────────────────────────────────────────────────
    header("Test 2: SPEED:200 komutu")
    resp = send_cmd(ser, "SPEED:200")
    info(f"Cevap: '{resp}'")
    if "OK" in resp:
        ok("Hız ayarlandı (200 adım/sn)")
    else:
        fail(f"SPEED komutu hata verdi: '{resp}'")
        all_passed = False

    # ── Test 3: START ───────────────────────────────────────────────────────
    header("Test 3: START komutu — Motor 3 saniye dönecek")
    warn("Motor şimdi dönmeli! STEP pinindeki LED yanıp sönmeli...")
    resp = send_cmd(ser, "START")
    info(f"Cevap: '{resp}'")
    if "OK" in resp:
        ok("START komutu kabul edildi")
        print("\n  *** 3 saniye bekleniyor — motoru izleyin ***")
        for i in range(3, 0, -1):
            print(f"  {i}...", end="\r", flush=True)
            time.sleep(1)
        print()
    else:
        fail(f"START komutu hata verdi: '{resp}'")
        all_passed = False

    # ── Test 4: STATUS (çalışırken) ─────────────────────────────────────────
    header("Test 4: STATUS (motor çalışırken)")
    resp = send_cmd(ser, "STATUS")
    info(f"Cevap: '{resp}'")
    if "running" in resp:
        ok("Motor çalışıyor olarak raporlandı")
    else:
        warn(f"Beklenen 'running', gelen: '{resp}'")

    # ── Test 5: STOP ────────────────────────────────────────────────────────
    header("Test 5: STOP komutu")
    resp = send_cmd(ser, "STOP")
    info(f"Cevap: '{resp}'")
    if "OK" in resp:
        ok("STOP komutu çalışıyor")
    else:
        fail(f"STOP komutu hata verdi: '{resp}'")
        all_passed = False

    # ── Test 6: Düşük/yüksek hız ────────────────────────────────────────────
    header("Test 6: Hız değiştirme testi (50 → 500 adım/sn)")
    for speed in [50, 100, 300, 500]:
        r1 = send_cmd(ser, f"SPEED:{speed}")
        r2 = send_cmd(ser, "START")
        time.sleep(0.5)
        r3 = send_cmd(ser, "STOP")
        status = "✓" if "OK" in r2 else "✗"
        print(f"    {status} {speed:4d} adım/sn → {r2}")
        time.sleep(0.2)

    # ── Özet ────────────────────────────────────────────────────────────────
    ser.close()
    header("─" * 40)
    if all_passed:
        ok(f"{GREEN}{BOLD}Tüm testler GEÇTI! Motor ve firmware çalışıyor.{RESET}")
        print(f"\n  Sıradaki adım: Uygulamayı aç → Dashboard → Başlat butonunu kullan\n")
    else:
        fail("Bazı testler BAŞARISIZ — yukarıdaki hataları inceleyin")
    return all_passed


# ── Ana giriş noktası ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Arduino pompa motor test scripti")
    parser.add_argument("--port",     help="Serial port (örn: /dev/cu.usbserial-A5069RR4)")
    parser.add_argument("--baud",     type=int, default=9600, help="Baudrate (varsayılan: 9600)")
    parser.add_argument("--auto",     action="store_true", help="Portu otomatik bul")
    parser.add_argument("--list",     action="store_true", help="Mevcut portları listele")
    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    port = args.port

    if not port or args.auto:
        found, desc = find_arduino_port()
        if found:
            info(f"Arduino bulundu: {found} ({desc})")
            port = found
        else:
            warn("Arduino otomatik bulunamadı. Mevcut portlar:")
            list_ports()
            print(f"\n  Kullanım: python scripts/test_motor.py --port /dev/cu.usbserial-XXXXX\n")
            sys.exit(1)

    run_tests(port, args.baud)


if __name__ == "__main__":
    main()
