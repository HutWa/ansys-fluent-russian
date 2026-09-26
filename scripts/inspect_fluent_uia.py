#!/usr/bin/env python3
"""Record read-only UIA facts for an approved Fluent navigation target.

The visual-QA runner deliberately refuses to capture a page unless its
heading was rendered.  This helper is the safe next step when that happens:
it sends no mouse, keyboard, Fluent journal, solver, or persistence action.
It merely writes the UI Automation structure exposed for one whitelisted
navigation-tree label so routes can be corrected from evidence.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # Support package import in tests and direct invocation by the task.
    from scripts.navigate_fluent_uia import SAFE_TARGETS, fluent_window
except ModuleNotFoundError:  # pragma: no cover - direct execution path.
    from navigate_fluent_uia import SAFE_TARGETS, fluent_window


def item_snapshot(item) -> dict[str, object]:
    """Return stable, non-invasive properties from a UIA wrapper."""
    rectangle = item.rectangle()
    info = item.element_info
    return {
        "name": item.window_text(),
        "control_type": info.control_type,
        "automation_id": info.automation_id,
        "class_name": info.class_name,
        "rectangle": {
            "left": rectangle.left,
            "top": rectangle.top,
            "right": rectangle.right,
            "bottom": rectangle.bottom,
        },
        "enabled": item.is_enabled(),
        "visible": item.is_visible(),
        "children": [
            {"name": child.window_text(), "control_type": child.element_info.control_type}
            for child in item.children()
            if child.window_text()
        ],
    }


def inspect_target(target: str) -> dict[str, object]:
    """Collect matching item and immediate parent facts without interaction."""
    label = SAFE_TARGETS[target]
    window = fluent_window()
    matches = [
        item for item in window.descendants(control_type="TreeItem")
        if item.window_text() == label
    ]
    return {
        "target": target,
        "label": label,
        "window": window.window_text(),
        "match_count": len(matches),
        "matches": [
            {
                "item": item_snapshot(item),
                "parent": item_snapshot(item.parent()),
            }
            for item in matches
        ],
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Fluent UIA target inspector")
    parser.add_argument("--target", choices=tuple(SAFE_TARGETS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot = inspect_target(args.target)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Inspected {snapshot['label']}: {snapshot['match_count']} matching tree item(s)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"Visual-QA UIA inspection error: {error}")
        raise SystemExit(2)
