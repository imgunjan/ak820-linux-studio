"""AK820 Linux Studio - native GUI and terminal commands."""

import argparse
from datetime import datetime
import sys

from .protocol import Keyboard, find_device, scan_interfaces


def do_probe():
    entries = scan_interfaces()
    if not entries:
        print(
            "No matching AJAZZ USB device found. Set wired mode and connect with a USB data cable."
        )
        return 1
    for entry in entries:
        print(
            f"{entry['path']}  VID:PID={entry['vendor']:04x}:{entry['product']:04x}  usage={entry['usage']:#06x}"
            if entry["usage"] is not None
            else f"{entry['path']}  usage=unknown"
        )
    try:
        pair = find_device()
        print(
            f"Compatible screen interfaces found: control {pair.control} / data {pair.data}"
        )
        return 0
    except RuntimeError as exc:
        print(f"Not compatible with this classic protocol: {exc}")
        return 2


def do_upload(
    path, fit="cover", max_frames=60, *, rotation=0, brightness=1.0, speed=1.0
):
    from .images import prepare_image

    prepared = prepare_image(
        path, fit, max_frames, rotation=rotation, brightness=brightness, speed=speed
    )
    print(f"Prepared {len(prepared.frames)} frame(s) from {path}")
    if prepared.truncated:
        print(f"Frame limit reached: using the first {max_frames} frames.")
    if prepared.timing_limited:
        print(
            "Some frame delays were limited to the keyboard's supported range (2–510 ms)."
        )
    pair = find_device()
    with Keyboard(pair) as dev:
        dev.upload(
            prepared.frames,
            prepared.delays,
            lambda pos, total: print(
                f"\rSending {pos}/{total} reports", end="", flush=True
            ),
        )
    print("\nTransfer completed; check the keyboard screen.")


def gui():
    try:
        from .gui import run_gui
    except ImportError as exc:
        raise RuntimeError(
            "GUI dependencies missing. Run ./setup.sh (python3-tk, Pillow)."
        ) from exc
    run_gui()


def main():
    parser = argparse.ArgumentParser(
        description="AJAZZ AK820 Pro Linux display control"
    )
    sub = parser.add_subparsers(dest="action")
    sub.add_parser("probe", help="Read-only USB device detection")
    sub.add_parser("clock", help="Send local system time to keyboard")
    p = sub.add_parser("upload", help="Upload PNG, JPG, BMP, WebP or animated GIF")
    p.add_argument("path")
    p.add_argument("--fit", choices=["cover", "contain", "stretch"], default="cover")
    p.add_argument("--max-frames", type=int, default=60)
    p.add_argument(
        "--rotate",
        type=int,
        choices=[0, 90, 180, 270],
        default=0,
        help="Rotate clockwise in degrees",
    )
    p.add_argument(
        "--brightness",
        type=float,
        default=1.0,
        help="Image brightness: 0 to 2 (default: 1)",
    )
    p.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="GIF speed multiplier: 0.25 to 4 (default: 1)",
    )
    sub.add_parser("gui", help="Open graphical application")
    args = parser.parse_args()
    try:
        if args.action == "probe":
            return do_probe()
        if args.action == "clock":
            pair = find_device()
            with Keyboard(pair) as dev:
                dev.sync_clock()
            print("Clock command sent.")
        elif args.action == "upload":
            do_upload(
                args.path,
                args.fit,
                args.max_frames,
                rotation=args.rotate,
                brightness=args.brightness,
                speed=args.speed,
            )
        else:
            gui()
        return 0
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
