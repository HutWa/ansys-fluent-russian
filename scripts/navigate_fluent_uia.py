#!/usr/bin/env python3
"""Open pre-approved Fluent task pages through Windows UI Automation.

Only navigation-tree selection and Enter are sent.  In particular, this
helper contains no solver, model, material, mesh, save, or calculation action.
It is intended for read-only visual QA of an already-loaded copied case.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path


SAFE_TARGETS = {
    "run-calculation": "Запуск расчёта",
    "models-tree": "Модели",
    "solution-methods": "Методы",
    "solution-controls": "Управление",
}


def fluent_window():
    """Return the ready Fluent@Home window without choosing splash windows."""
    try:
        from pywinauto import Desktop
    except ModuleNotFoundError as error:  # pragma: no cover - host prerequisite.
        raise RuntimeError("pywinauto is required for Windows UI Automation") from error
    windows = [window for window in Desktop(backend="uia").windows() if "fluent@home" in window.window_text().casefold()]
    if not windows:
        raise RuntimeError("No ready Fluent@Home window is open")
    return max(windows, key=lambda window: window.rectangle().width() * window.rectangle().height())


def matching_tree_item(window, label: str):
    """Find one visible UIA tree item by its exact rendered name."""
    matches = [item for item in window.descendants(control_type="TreeItem") if item.window_text() == label]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one tree item named {label!r}; found {len(matches)}")
    return matches[0]


def open_target(target: str, settle_seconds: float) -> dict[str, str]:
    """Select a whitelisted task page and wait for Fluent to render it."""
    label = SAFE_TARGETS[target]
    window = fluent_window()
    item = matching_tree_item(window, label)
    # Fluent exposes tree names but not UIA selection/scroll patterns.  Use the
    # observed item rectangle only to scroll the navigation pane, then re-find
    # and click the now-visible whitelisted row.
    from pywinauto import mouse
    window_bottom = window.rectangle().bottom
    if item.rectangle().bottom > window_bottom - 100:
        mouse.scroll(coords=(120, window_bottom - 180), wheel_dist=-12)
        time.sleep(0.8)
        item = matching_tree_item(window, label)
    if target == "models-tree":
        # Fluent exposes no UIA ExpandCollapse pattern for this tree item.
        # The tiny expander is immediately to the left of its *actual UIA*
        # bounds; derive that point at runtime instead of using a screen
        # coordinate.  Reject an implausible point before sending a click.
        from pywinauto import mouse
        item_rect = item.rectangle()
        expander_x = item_rect.left - 12
        expander_y = item_rect.top + item_rect.height() // 2
        window_rect = window.rectangle()
        if not (window_rect.left < expander_x < item_rect.left and window_rect.top < expander_y < window_rect.bottom):
            raise RuntimeError("Models tree expander is outside the ready Fluent window")
        mouse.click(button="left", coords=(expander_x, expander_y))
        action = "expand-by-derived-expander"
    else:
        item.double_click_input()
        item.type_keys("{ENTER}")
        action = "open"
    time.sleep(settle_seconds)
    trace = {"target": target, "label": label, "action": action, "window": window.window_text()}
    if target == "models-tree":
        trace["expander_point"] = f"{expander_x},{expander_y}"
    return trace


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe Fluent UIA task-page navigation")
    parser.add_argument("--target", choices=tuple(SAFE_TARGETS), required=True)
    parser.add_argument("--settle-seconds", type=float, default=8)
    parser.add_argument("--trace-file", type=Path)
    args = parser.parse_args()
    if args.settle_seconds <= 0:
        parser.error("settle seconds must be positive")
    trace = open_target(args.target, args.settle_seconds)
    trace["finished_at"] = datetime.now(timezone.utc).isoformat()
    if args.trace_file:
        args.trace_file.parent.mkdir(parents=True, exist_ok=True)
        args.trace_file.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Opened {trace['label']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"Visual-QA UIA navigation error: {error}")
        raise SystemExit(2)
