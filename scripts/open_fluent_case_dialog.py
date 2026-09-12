#!/usr/bin/env python3
"""Open Fluent's file-selection dialog for visual QA without reading a case."""
from __future__ import annotations

import ctypes
import time

from navigate_fluent_visual_qa import wait_for_window


VK_CONTROL = 0x11
VK_O = 0x4F
KEYEVENTF_KEYUP = 0x0002


def main() -> int:
    hwnd, title, _ = wait_for_window(45)
    user32 = ctypes.windll.user32
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_O, 0, 0, 0)
    user32.keybd_event(VK_O, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    print(f"Requested case-open dialog from: {title}")
    time.sleep(3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
