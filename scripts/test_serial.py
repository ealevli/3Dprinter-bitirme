"""
test_serial.py — Quick serial connection tester.

Usage:
    python scripts/test_serial.py --port /dev/ttyUSB0 --baud 115200 --target printer
    python scripts/test_serial.py --port /dev/ttyACM0 --baud 9600  --target pump
"""

import argparse
import sys
import time

import serial
import serial.tools.list_ports


def list_ports() -> None:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return
    print("Available ports:")
    for p in ports:
        print(f"  {p.device:20s} — {p.description}")


def test_printer(port: str, baud: int) -> None:
    print(f"Connecting to printer at {port} ({baud} baud)…")
    with serial.Serial(port, baud, timeout=5) as ser:
        time.sleep(2)
        boot = ser.readline().decode(errors="replace").strip()
        print(f"Boot message: {boot!r}")

        cmd = "M115\n"   # firmware info
        ser.write(cmd.encode())
        print(f"Sent: {cmd.strip()!r}")
        for _ in range(5):
            line = ser.readline().decode(errors="replace").strip()
            if line:
                print(f"  <- {line!r}")
            if line == "ok":
                break
    print("Printer test done.")


def test_pump(port: str, baud: int) -> None:
    print(f"Connecting to pump (Arduino) at {port} ({baud} baud)…")
    with serial.Serial(port, baud, timeout=5) as ser:
        time.sleep(1.5)
        ser.write(b"STATUS\n")
        print("Sent: STATUS")
        resp = ser.readline().decode(errors="replace").strip()
        print(f"  <- {resp!r}")
    print("Pump test done.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="List available ports and exit")
    parser.add_argument("--port", default=None)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--target", choices=["printer", "pump"], default="printer")
    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    if not args.port:
        print("Specify --port or use --list to see available ports.")
        list_ports()
        sys.exit(1)

    if args.target == "printer":
        test_printer(args.port, args.baud)
    else:
        test_pump(args.port, args.baud)


if __name__ == "__main__":
    main()
