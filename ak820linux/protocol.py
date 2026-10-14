"""Linux hidraw transport for AJAZZ AK820 Pro (stock firmware, classic HID protocol).

Protocol implemented from public reverse-engineering notes by
Beattrey/ajazz-ak820-config and aar-rafi/aks075-linux. No firmware updates.
Only uses USB HID 0x0c45:0x8009/0x800a; requires usage pages FF13 & FF68.

WARNING: Hardware-dependent, untested on this developer's physical keyboard.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import fcntl
import os
import select
import time
from dataclasses import dataclass
from typing import Callable

VENDOR = 0x0C45
PRODUCTS = {0x8009, 0x800A}
CONTROL_USAGE = 0xFF13
DATA_USAGE = 0xFF68
FRAME_BYTES = 128 * 128 * 2
CHUNK_SIZE = 4096
SYS_HIDRAW = Path("/sys/class/hidraw")


def _usage_page(descriptor: bytes) -> int | None:
    """Get first vendor HID Usage Page (descriptor may have multiple sections)."""
    pages = []
    i = 0
    while i < len(descriptor):
        item = descriptor[i]
        if item == 0xFE:  # HID long item
            if i + 3 > len(descriptor):
                break
            i += 3 + descriptor[i + 1]
            continue
        size = (0, 1, 2, 4)[item & 3]
        if i + 1 + size > len(descriptor):
            break
        if item & 0xFC == 0x04 and size:
            page = int.from_bytes(descriptor[i + 1 : i + 1 + size], "little")
            pages.append(page)
        i += 1 + size
    for page in pages:
        if page in (CONTROL_USAGE, DATA_USAGE):
            return page
    return None


@dataclass(frozen=True)
class InterfacePair:
    vendor: int
    product: int
    control: Path
    data: Path


def _usb_identity(uevent: str) -> tuple[int, int] | None:
    for line in uevent.splitlines():
        if line.startswith("HID_ID="):
            try:
                _bus, vendor, product = line[7:].split(":")
                return int(vendor, 16), int(product, 16)
            except ValueError:
                return None
    return None


def scan_interfaces(sys_root: Path = SYS_HIDRAW) -> list[dict]:
    """Read-only discovery; no vendor requests are sent."""
    results = []
    if not sys_root.exists():
        return results
    for entry in sorted(sys_root.glob("hidraw*")):
        try:
            identity = _usb_identity((entry / "device/uevent").read_text())
            if identity is None or identity[0] != VENDOR or identity[1] not in PRODUCTS:
                continue
            desc = (entry / "device/report_descriptor").read_bytes()
            results.append(
                {
                    "path": Path("/dev") / entry.name,
                    "vendor": identity[0],
                    "product": identity[1],
                    "usage": _usage_page(desc),
                }
            )
        except (OSError, ValueError):
            continue
    return results


def find_device(sys_root: Path = SYS_HIDRAW) -> InterfacePair:
    interfaces = scan_interfaces(sys_root)
    for pid in sorted(PRODUCTS):
        control = next(
            (
                x
                for x in interfaces
                if x["product"] == pid and x["usage"] == CONTROL_USAGE
            ),
            None,
        )
        data = next(
            (x for x in interfaces if x["product"] == pid and x["usage"] == DATA_USAGE),
            None,
        )
        if control and data:
            return InterfacePair(VENDOR, pid, control["path"], data["path"])
    if interfaces:
        lines = ", ".join(f"{i['path']}:usage={i['usage']!r}" for i in interfaces)
        raise RuntimeError(
            f"Found an AJAZZ/Sonix USB device, but not the required FF13+FF68 screen interfaces. {lines}. This firmware may use a different protocol."
        )
    raise RuntimeError(
        "AK820 Pro not detected (expected USB VID 0c45, PID 8009 or 800a). Connect a USB data cable, switch to wired mode, and run lsusb."
    )


def command_packet(cmd: int, sub: int = 0, flag: int = 1) -> bytes:
    b = bytearray(64)
    b[0], b[1], b[2], b[8] = 4, cmd, sub, flag
    return bytes(b)


def time_data_packet(dt: datetime) -> bytes:
    if not (2000 <= dt.year <= 2255):
        raise ValueError("Year out of 8-bit range")
    b = bytearray(64)
    b[0:3] = b"\x00\x01\x5a"
    b[3:9] = bytes((dt.year - 2000, dt.month, dt.day, dt.hour, dt.minute, dt.second))
    b[10] = 4
    b[62:64] = b"\xaa\x55"
    return bytes(b)


def image_header(delays_ms: list[int] | None = None) -> bytes:
    delays = [0] if delays_ms is None else delays_ms
    if not (1 <= len(delays) <= 255):
        raise ValueError("Frame count must be 1 to 255")
    hdr = bytearray(b"\xff" * 256)
    hdr[0] = len(delays)
    for i, delay in enumerate(delays):
        hdr[i + 1] = 0 if len(delays) == 1 else max(1, min(255, round(delay / 2)))
    return bytes(hdr)


def image_payload(frames: list[bytes], delays_ms: list[int] | None = None) -> bytes:
    if not (1 <= len(frames) <= 255):
        raise ValueError("Expected 1 to 255 frames")
    if any(len(frame) != FRAME_BYTES for frame in frames):
        raise ValueError(f"Every frame must contain {FRAME_BYTES} RGB565 bytes")
    if delays_ms is not None and len(delays_ms) != len(frames):
        raise ValueError("Frame/delay counts do not match")
    payload = image_header(delays_ms if len(frames) > 1 else None) + b"".join(frames)
    pad = (-len(payload)) % CHUNK_SIZE
    return payload + b"\xff" * pad


def _ioctl_request(report_number: int, report_length: int = 65) -> int:
    # Linux HIDIOCSFEATURE/HIDIOCGFEATURE = _IOC(_IOC_READ|_IOC_WRITE, 'H', n, length)
    return 0xC0000000 | (report_length << 16) | (ord("H") << 8) | report_number


class Keyboard:
    def __init__(self, pair: InterfacePair):
        self.pair = pair
        self.control_fd: int | None = None
        self.data_fd: int | None = None

    def __enter__(self):
        try:
            self.control_fd = os.open(self.pair.control, os.O_RDWR)
            self.data_fd = os.open(self.pair.data, os.O_RDWR)
        except OSError as exc:
            self.__exit__(None, None, None)
            if isinstance(exc, PermissionError):
                raise PermissionError(
                    "Access denied to hidraw. Run ./install-udev.sh once, then unplug/reconnect USB."
                ) from exc
            raise
        return self

    def __exit__(self, *_args):
        for field in ("control_fd", "data_fd"):
            fd = getattr(self, field)
            if fd is not None:
                os.close(fd)
                setattr(self, field, None)

    def send_feature(self, payload: bytes):
        if self.control_fd is None or len(payload) != 64:
            raise ValueError("Feature payload must be 64 bytes and device must be open")
        # Report ID 0x00, followed by 64-byte command payload.
        fcntl.ioctl(self.control_fd, _ioctl_request(0x06), b"\x00" + payload)
        time.sleep(0.04)

    def handshake(self):
        if self.control_fd is None:
            raise RuntimeError("Not connected")
        try:
            buf = bytearray(65)
            fcntl.ioctl(self.control_fd, _ioctl_request(0x07), buf, True)
        except OSError:
            pass  # USB firmware revisions vary; read-back is advisory

    def sync_clock(self, dt: datetime | None = None):
        dt = dt or datetime.now()
        self.send_feature(command_packet(0x18, flag=1))
        self.send_feature(command_packet(0x28, flag=1))
        self.handshake()
        self.send_feature(time_data_packet(dt))
        self.send_feature(command_packet(0x02, flag=0))
        self.handshake()

    def _write_data(self, data: bytes):
        if self.data_fd is None or len(data) != CHUNK_SIZE:
            raise ValueError("Data report must contain exactly 4096 bytes")
        # hidraw consumes a leading zero report ID; device receives exactly 4096 bytes.
        buf = b"\x00" + data
        written = os.write(self.data_fd, buf)
        if written != len(buf):
            # HID reports are atomic; never send the remainder as a new report.
            raise OSError(f"Incomplete USB HID report: sent {written}/{len(buf)} bytes")

    def _read_ack(self):
        if self.data_fd is None:
            raise RuntimeError("Not connected")
        ready, _, _ = select.select([self.data_fd], [], [], 0.30)
        if ready:
            try:
                return os.read(self.data_fd, 64)
            except BlockingIOError:
                pass
        return None

    def upload(
        self,
        frames: list[bytes],
        delays_ms: list[int] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ):
        payload = image_payload(frames, delays_ms)
        chunks = len(payload) // CHUNK_SIZE
        if chunks > 65535:
            raise ValueError("Image payload too large")
        self.send_feature(command_packet(0x18, flag=0))
        self.handshake()
        cfg = bytearray(command_packet(0x72, sub=0x03, flag=0))
        cfg[8:10] = chunks.to_bytes(2, "little")
        self.send_feature(bytes(cfg))
        self.handshake()
        for idx in range(chunks):
            self._write_data(payload[idx * CHUNK_SIZE : (idx + 1) * CHUNK_SIZE])
            self._read_ack()
            if on_progress:
                on_progress(idx + 1, chunks)
        self.send_feature(command_packet(0x02, flag=0))
        self.handshake()
