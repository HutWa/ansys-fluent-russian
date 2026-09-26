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
    "solution-initialization": "Инициализация",
    "materials": "Материалы",
    "cell-zone-conditions": "Условия в ячеечных зонах",
}

TARGET_PAGE_HEADINGS = {
    "run-calculation": "Запуск расчёта",
    "solution-methods": "Методы решения",
    "solution-controls": "Управление решением",
    "solution-initialization": "Инициализация решения",
    "materials": "Материалы",
    "cell-zone-conditions": "Условия ячеечных зон",
}

# The UIA probe on the loaded v261 bioreactor case confirms these are visible
# Kept as a named empty allowlist: targets are added only after a visual QA
# run proves that a single click is the only safe way to open their page.
SINGLE_CLICK_TARGETS = frozenset()

EXPANDABLE_TARGETS = {
    "materials": "Жидкость",
    "cell-zone-conditions": "fluid_mrf",
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


def write_rendered_text_dump(window, output: Path) -> None:
    """Record live UIA text and bounds to diagnose a safe navigation failure."""
    rows: list[dict[str, object]] = []
    for item in window.descendants():
        text = item.window_text()
        if not text:
            continue
        rect = item.rectangle()
        try:
            selected = bool(item.iface_selection_item.CurrentIsSelected)
        except Exception:  # UIA selection is not available for most controls.
            selected = False
        rows.append({
            "text": text,
            "control_type": item.element_info.control_type,
            "selected": selected,
            "left": rect.left,
            "top": rect.top,
            "right": rect.right,
            "bottom": rect.bottom,
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def assert_target_page(window, target: str, debug_file: Path | None = None) -> str:
    """Classify page evidence without claiming custom-painted content was inspected."""
    expected = TARGET_PAGE_HEADINGS.get(target)
    if expected is None:
        return
    # The navigation tree and the task page both expose labels such as
    # "Материалы".  A window-wide text search would therefore treat merely
    # selecting a tree item as proof that the page opened.  Task Page starts
    # to the right of roughly one fifth of the Fluent window; only count
    # labels rendered in that content area, below the ribbon.
    rect = window.rectangle()
    content_left = rect.left + round(rect.width() * 0.18)
    content_top = rect.top + round(rect.height() * 0.18)
    rendered = {
        item.window_text() for item in window.descendants()
        if item.window_text() and item.rectangle().left >= content_left and item.rectangle().top >= content_top
    }
    if debug_file is not None:
        write_rendered_text_dump(window, debug_file)
    if expected in rendered:
        return "uia-content-heading"
    # Several Fluent v261 task pages are custom-painted and expose neither
    # their central text nor tree selection state through UIA.  The preceding
    # whitelisted action is therefore enough to permit an automatic *capture*,
    # but is deliberately weaker evidence than a readable heading.  A visual
    # QA record may use this only as ``captured``/``needs_recheck`` evidence,
    # never as a reason to mark the page verified.
    return "custom-painted-content-unavailable; capture-required"


def click_derived_expander(window, item) -> str:
    """Expand a visible tree row using only its live UIA geometry."""
    from pywinauto import mouse
    item_rect = item.rectangle()
    expander_x = item_rect.left - 12
    expander_y = item_rect.top + item_rect.height() // 2
    window_rect = window.rectangle()
    if not (window_rect.left < expander_x < item_rect.left and window_rect.top < expander_y < window_rect.bottom):
        raise RuntimeError("Tree expander is outside the ready Fluent window")
    mouse.click(button="left", coords=(expander_x, expander_y))
    return f"{expander_x},{expander_y}"


def expand_target(target: str, settle_seconds: float) -> dict[str, str]:
    """Expand one whitelisted navigation branch without opening any page."""
    if target not in EXPANDABLE_TARGETS:
        raise RuntimeError(f"Target cannot be expanded safely: {target}")
    label = SAFE_TARGETS[target]
    window = fluent_window()
    item = matching_tree_item(window, label)
    child = EXPANDABLE_TARGETS[target]
    visible_children = {candidate.window_text() for candidate in window.descendants(control_type="TreeItem")}
    if child in visible_children:
        action, expander_point = "already-expanded", None
    else:
        expander_point = click_derived_expander(window, item)
        time.sleep(settle_seconds)
        action = "expand-by-derived-expander"
    if not any(candidate.window_text() == child for candidate in window.descendants(control_type="TreeItem")):
        raise RuntimeError(f"Fluent did not render expected child after expanding {label}: {child}")
    trace = {
        "target": target,
        "label": label,
        "action": action,
        "window": window.window_text(),
    }
    if expander_point is not None:
        trace["expander_point"] = expander_point
    return trace


def open_target(target: str, settle_seconds: float, debug_file: Path | None = None) -> dict[str, str]:
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
        expander_point = click_derived_expander(window, item)
        action = "expand-by-derived-expander"
    elif target == "materials":
        # The parent row only expands the category.  The read-only UIA probe
        # established that its Russian child is the actual Fluid page entry.
        expand_target("materials", settle_seconds)
        item = matching_tree_item(window, EXPANDABLE_TARGETS["materials"])
        item.double_click_input()
        action = "open-materials-fluid-list"
    elif target in SINGLE_CLICK_TARGETS:
        item.click_input()
        action = "select-once"
    else:
        item.double_click_input()
        item.type_keys("{ENTER}")
        action = "open"
    time.sleep(settle_seconds)
    verification = assert_target_page(window, target, debug_file)
    trace = {
        "target": target,
        "label": label,
        "action": action,
        "page_verification": verification,
        "window": window.window_text(),
    }
    if target == "models-tree":
        trace["expander_point"] = expander_point
    return trace


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe Fluent UIA task-page navigation")
    parser.add_argument("--target", choices=tuple(SAFE_TARGETS), required=True)
    parser.add_argument("--expand", action="store_true", help="Expand one whitelisted tree branch without opening a page")
    parser.add_argument("--settle-seconds", type=float, default=8)
    parser.add_argument("--trace-file", type=Path)
    parser.add_argument("--debug-file", type=Path, help="Write live UIA text and bounds after navigation")
    args = parser.parse_args()
    if args.settle_seconds <= 0:
        parser.error("settle seconds must be positive")
    trace = expand_target(args.target, args.settle_seconds) if args.expand else open_target(args.target, args.settle_seconds, args.debug_file)
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
