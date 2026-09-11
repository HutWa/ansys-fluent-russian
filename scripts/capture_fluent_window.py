#!/usr/bin/env python3
"""Capture Fluent windows for local visual QA without third-party packages.

The tool uses only Windows GDI through ctypes. Captures and their manifest are
local build artifacts: do not commit them to the repository.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import struct
import sys
import time
import zlib
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
PW_RENDERFULLCONTENT = 2
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [("rgbBlue", ctypes.c_ubyte), ("rgbGreen", ctypes.c_ubyte), ("rgbRed", ctypes.c_ubyte), ("rgbReserved", ctypes.c_ubyte)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_png_bgra(width: int, height: int, pixels: bytes) -> bytes:
    """Encode a top-down BGRA bitmap as a simple RGBA PNG."""
    if len(pixels) != width * height * 4:
        raise ValueError("Unexpected bitmap size")
    scanlines = bytearray()
    for row in range(height):
        scanlines.append(0)
        start = row * width * 4
        for offset in range(start, start + width * 4, 4):
            blue, green, red = pixels[offset : offset + 3]
            scanlines.extend((red, green, blue, 255))
    return b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + png_chunk(b"IDAT", zlib.compress(bytes(scanlines), 9)) + png_chunk(b"IEND", b"")


def require_windows() -> None:
    if os.name != "nt":
        raise OSError("Visual capture is available only on Windows")


def window_titles() -> list[tuple[int, str]]:
    require_windows()
    user32 = ctypes.windll.user32
    found: list[tuple[int, str]] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def collect(hwnd: int, _: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if not length:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        found.append((int(hwnd), buffer.value))
        return True

    if not user32.EnumWindows(collect, 0):
        raise OSError("EnumWindows failed; run the watcher from an interactive Windows desktop session")
    return found


def find_windows(title_contains: str) -> list[tuple[int, str]]:
    needle = title_contains.casefold()
    return [(hwnd, title) for hwnd, title in window_titles() if needle in title.casefold()]


def capture_bgra(hwnd: int) -> tuple[int, int, bytes]:
    require_windows()
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise OSError("GetWindowRect failed")
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise ValueError("Window has no visible area")
    source = user32.GetWindowDC(hwnd)
    if not source:
        raise OSError("GetWindowDC failed")
    memory_dc = gdi32.CreateCompatibleDC(source)
    if not memory_dc:
        user32.ReleaseDC(hwnd, source)
        raise OSError("CreateCompatibleDC failed")
    bitmap = None
    previous = None
    try:
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # top-down DIB
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(source, ctypes.byref(info), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
        if not bitmap or not bits.value:
            raise OSError("CreateDIBSection failed")
        previous = gdi32.SelectObject(memory_dc, bitmap)
        rendered = bool(user32.PrintWindow(hwnd, memory_dc, PW_RENDERFULLCONTENT))
        if not rendered and not gdi32.BitBlt(memory_dc, 0, 0, width, height, source, 0, 0, SRCCOPY):
            raise OSError("PrintWindow and BitBlt failed")
        return width, height, ctypes.string_at(bits, width * height * 4)
    finally:
        if previous:
            gdi32.SelectObject(memory_dc, previous)
        if bitmap:
            gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, source)


def safe_name(value: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9А-Яа-я_-]+", "-", value).strip("-")
    return compact[:72] or "fluent"


def load_manifest(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("capture manifest must be an array")
    return data


def capture_windows(windows: Iterable[tuple[int, str]], output: Path, previous_hashes: set[str]) -> list[dict[str, object]]:
    output.mkdir(parents=True, exist_ok=True)
    created: list[dict[str, object]] = []
    for hwnd, title in windows:
        width, height, pixels = capture_bgra(hwnd)
        image = encode_png_bgra(width, height, pixels)
        digest = hashlib.sha256(image).hexdigest()
        if digest in previous_hashes:
            continue
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{timestamp}-{safe_name(title)}-{digest[:12]}.png"
        (output / filename).write_bytes(image)
        created.append({"captured_at": timestamp, "title": title, "file": filename, "sha256": digest, "width": width, "height": height})
        previous_hashes.add(digest)
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture visible Fluent windows for local visual QA")
    parser.add_argument("--title-contains", default="fluent", help="Case-insensitive Fluent window-title fragment")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build" / "visual-qa")
    parser.add_argument("--list-windows", action="store_true", help="Print matching visible windows and exit")
    parser.add_argument("--watch", action="store_true", help="Capture changed matching windows until interrupted")
    parser.add_argument("--interval", type=float, default=3.0, help="Watch interval in seconds")
    parser.add_argument(
        "--exit-when-closed", action="store_true",
        help="In watch mode, exit after a seen Fluent window remains closed for --close-grace seconds",
    )
    parser.add_argument("--close-grace", type=float, default=12.0, help="Seconds to wait after Fluent closes")
    args = parser.parse_args()
    if args.interval <= 0 or args.close_grace <= 0:
        parser.error("--interval and --close-grace must be positive")
    try:
        if args.list_windows:
            matches = find_windows(args.title_contains)
            for hwnd, title in matches:
                print(f"{hwnd}: {title}")
            return 0 if matches else 1
        manifest_path = args.output_dir / "capture-manifest.json"
        manifest = load_manifest(manifest_path)
        hashes = {str(item.get("sha256")) for item in manifest if item.get("sha256")}
        has_seen_window = False
        closed_since: float | None = None
        while True:
            matches = find_windows(args.title_contains)
            if matches:
                has_seen_window = True
                closed_since = None
            elif args.exit_when_closed and has_seen_window:
                if closed_since is None:
                    closed_since = time.monotonic()
                    print("Fluent closed; stopping visual-QA watcher after grace period.")
                elif time.monotonic() - closed_since >= args.close_grace:
                    return 0
            new_entries = capture_windows(matches, args.output_dir, hashes)
            if new_entries:
                manifest.extend(new_entries)
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                for entry in new_entries:
                    print(f"Captured: {entry['file']}")
            if not args.watch:
                return 0 if new_entries else 1
            time.sleep(args.interval)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
