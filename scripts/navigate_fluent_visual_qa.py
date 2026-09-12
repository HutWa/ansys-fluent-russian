#!/usr/bin/env python3
"""Navigate a freshly started Fluent home screen for visual QA.

This helper deliberately performs only left-clicks on visible navigation-tree
rows.  It neither opens a case nor changes, saves, initializes, or calculates
anything.  It is intended to be launched in the interactive Windows session
by ``run_visual_qa_task.cmd``; the normal window watcher records the frames.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

try:  # Support both direct execution and imports by the test suite.
    from scripts.capture_fluent_window import RECT, find_windows
except ModuleNotFoundError:  # pragma: no cover - exercised by the direct CLI smoke test.
    from capture_fluent_window import RECT, find_windows


MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002
VK_RETURN = 0x0D
VK_RIGHT = 0x27


# Coordinates are fractions of the maximized Fluent home window captured on
# the test workstation.  They target only already-visible tree items.
HOME_STEPS = (
    ("materials", 0.060, 0.351),
    ("graphics", 0.060, 0.418),
    ("surfaces", 0.060, 0.401),
)
PHYSICS_RIBBON_STEPS = (("physics-ribbon", 0.160, 0.047),)
MULTIPHASE_DIALOG_STEPS = PHYSICS_RIBBON_STEPS + (
    ("multiphase-model", 0.380, 0.105),
    ("multiphase-open", 0.380, 0.105),
)
FILE_RIBBON_STEPS = (("file-ribbon", 0.030, 0.047),)
MODELS_EXPAND_STEPS = (("models-expand", 0.030, 0.347),)
MULTIPHASE_TREE_STEPS = MODELS_EXPAND_STEPS + (("multiphase-tree", 0.100, 0.366),)
MATERIALS_TREE_STEPS = (
    ("materials-tree", 0.100, 0.622),
    ("materials-open", 0.100, 0.622),
)


def select_home_window(candidates: list[tuple[int, str, RECT]]) -> tuple[int, str, RECT] | None:
    """Prefer the actual Fluent@Home session over splash and error windows."""
    home = [item for item in candidates if "@home" in item[1].casefold()]
    return max(home, key=lambda item: (item[2].right - item[2].left) * (item[2].bottom - item[2].top), default=None)


def largest_fluent_window(title_contains: str = "fluent") -> tuple[int, str, RECT] | None:
    """Return a visible ready Fluent@Home top-level window, if present."""
    if os.name != "nt":
        raise OSError("Interactive visual navigation is available only on Windows")
    user32 = ctypes.windll.user32
    candidates: list[tuple[int, str, RECT]] = []
    for hwnd, title in find_windows(title_contains):
        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            continue
        if rect.right > rect.left and rect.bottom > rect.top:
            candidates.append((hwnd, title, rect))
    return select_home_window(candidates)


def click_window_fraction(hwnd: int, rect: RECT, x_fraction: float, y_fraction: float, click_count: int = 2) -> tuple[int, int]:
    """Send a real double click at a window-relative point on the active desktop."""
    user32 = ctypes.windll.user32
    width, height = rect.right - rect.left, rect.bottom - rect.top
    x = rect.left + round(width * x_fraction)
    y = rect.top + round(height * y_fraction)
    user32.SetForegroundWindow(hwnd)
    user32.SetCursorPos(x, y)
    for _ in range(click_count):
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.08)
    return x, y


def confirm_tree_selection() -> None:
    """Ask Fluent to open the already-selected tree page, without editing it."""
    user32 = ctypes.windll.user32
    user32.keybd_event(VK_RETURN, 0, 0, 0)
    user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)


def press_right() -> None:
    """Expand an already-selected tree node without opening a page."""
    user32 = ctypes.windll.user32
    user32.keybd_event(VK_RIGHT, 0, 0, 0)
    user32.keybd_event(VK_RIGHT, 0, KEYEVENTF_KEYUP, 0)


def wait_for_window(timeout: float) -> tuple[int, str, RECT]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        window = largest_fluent_window()
        if window is not None:
            return window
        time.sleep(1)
    raise TimeoutError("Fluent window did not appear before the visual-QA timeout")


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe coordinate navigation for Fluent visual QA")
    parser.add_argument("--wait-seconds", type=float, default=45, help="Maximum time to wait for Fluent")
    parser.add_argument("--settle-seconds", type=float, default=8, help="Delay after each navigation click")
    parser.add_argument("--mode", choices=("home", "physics-ribbon", "multiphase-dialog", "multiphase-tree", "materials-tree", "file-ribbon", "models-expand"), default="home", help="Safe visual-QA navigation route")
    parser.add_argument("--trace-file", type=Path, help="Write the actual click trace as a local build artifact")
    parser.add_argument("--dry-run", action="store_true", help="Print the navigation plan without clicking")
    args = parser.parse_args()
    if args.wait_seconds <= 0 or args.settle_seconds <= 0:
        parser.error("wait and settle durations must be positive")

    if args.dry_run:
        steps = route_steps(args.mode)
        for name, x, y in steps:
            print(f"{name}: {x:.3f}, {y:.3f}")
        return 0

    ctypes.windll.user32.SetProcessDPIAware()
    hwnd, title, rect = wait_for_window(args.wait_seconds)
    trace = {"window": title, "started_at": datetime.now(timezone.utc).isoformat(), "steps": []}
    steps = route_steps(args.mode)
    trace["mode"] = args.mode
    for name, x_fraction, y_fraction in steps:
        if args.mode == "home":
            x, y = click_window_fraction(hwnd, rect, x_fraction, y_fraction)
            confirm_tree_selection()
            trace["steps"].append({"name": name, "screen_x": x, "screen_y": y, "click_count": 2, "key": "Enter", "captured_after_seconds": args.settle_seconds})
            print(f"Double-clicked and confirmed {name}: {x}, {y}")
        else:
            click_count = 2 if name == "materials-tree" else 1
            x, y = click_window_fraction(hwnd, rect, x_fraction, y_fraction, click_count=click_count)
            key = None
            if name == "multiphase-open":
                confirm_tree_selection()
                key = "Enter"
            elif name == "multiphase-tree":
                confirm_tree_selection()
                key = "Enter"
            elif name == "materials-tree":
                confirm_tree_selection()
                key = "Enter"
            elif name == "materials-open":
                confirm_tree_selection()
                key = "Enter"
            elif name == "models-expand":
                press_right()
                key = "Right"
            entry = {"name": name, "screen_x": x, "screen_y": y, "click_count": click_count, "captured_after_seconds": args.settle_seconds}
            if key:
                entry["key"] = key
            trace["steps"].append(entry)
            print(f"Clicked {name}: {x}, {y}")
        time.sleep(args.settle_seconds)
    trace["finished_at"] = datetime.now(timezone.utc).isoformat()
    if args.trace_file:
        args.trace_file.parent.mkdir(parents=True, exist_ok=True)
        args.trace_file.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def route_steps(mode: str) -> tuple[tuple[str, float, float], ...]:
    routes = {
        "home": HOME_STEPS,
        "physics-ribbon": PHYSICS_RIBBON_STEPS,
        "multiphase-dialog": MULTIPHASE_DIALOG_STEPS,
        "multiphase-tree": MULTIPHASE_TREE_STEPS,
        "materials-tree": MATERIALS_TREE_STEPS,
        "file-ribbon": FILE_RIBBON_STEPS,
        "models-expand": MODELS_EXPAND_STEPS,
    }
    return routes[mode]


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, TimeoutError) as error:
        print(f"Visual-QA navigation error: {error}")
        raise SystemExit(2)
