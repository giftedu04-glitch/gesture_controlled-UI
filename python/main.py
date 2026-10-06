"""Entry point for the gesture-controlled desktop app."""

import argparse
import sys

from app import App
from serial_link import BluetoothLink


def main():
    parser = argparse.ArgumentParser(
        description="Colour-tracking gesture UI that talks to the Arduino over Bluetooth",
    )
    parser.add_argument("--camera", type=int, default=0, help="webcam index (default: 0)")
    parser.add_argument("--port", help="serial port of the Bluetooth module, e.g. COM3")
    parser.add_argument(
        "--threshold", type=int, default=50,
        help="colour match threshold, higher = looser (default: 50)",
    )
    parser.add_argument(
        "--list-serial", action="store_true", help="list available serial ports and exit",
    )
    args = parser.parse_args()

    if args.list_serial:
        ports = BluetoothLink.ports()
        print("\n".join(ports) if ports else "no serial ports found")
        return

    try:
        App(camera=args.camera, port=args.port, threshold=args.threshold).run()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
