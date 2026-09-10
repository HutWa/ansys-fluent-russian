#!/usr/bin/env python3
"""Apply a reviewed, project-authored translation batch to a catalog.

The batch is a JSON object mapping stable entry IDs to a translation string.
By default, only entries awaiting context or review may be promoted.  An
explicit flag also permits correcting already translated labels without a
large, mechanical catalog rewrite.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def object_bounds(text: str, entry_id: str) -> tuple[int, int]:
    """Return the JSON-object bounds that contain an exact entry-ID marker."""
    marker = re.compile(r'"id"\s*:\s*' + re.escape(json.dumps(entry_id, ensure_ascii=False)))
    match = marker.search(text)
    if not match:
        raise ValueError(f"Entry marker not found: {entry_id}")
    position = match.start()
    start = text.rfind("{", 0, position)
    if start < 0:
        raise ValueError(f"Object start not found for: {marker}")
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return start, index + 1
    raise ValueError(f"Object end not found for: {marker}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a translation batch")
    parser.add_argument("catalog", type=Path)
    parser.add_argument("batch", type=Path)
    parser.add_argument(
        "--replace-translated",
        action="store_true",
        help="replace the text of entries already marked translated or reviewed",
    )
    parser.add_argument(
        "--set-status",
        choices=("translated", "reviewed", "needs_context", "needs_review", "do_not_translate"),
        help="set a status while applying the batch",
    )
    args = parser.parse_args()

    original = args.catalog.read_text(encoding="utf-8")
    catalog = json.loads(original)
    batch = json.loads(args.batch.read_text(encoding="utf-8"))
    if not isinstance(batch, dict) or not all(isinstance(key, str) and isinstance(value, str) and value for key, value in batch.items()):
        raise ValueError("The batch must map entry IDs to non-empty translations.")

    entries = {entry["id"]: entry for entry in catalog["entries"]}
    unknown = sorted(set(batch) - set(entries))
    if unknown:
        raise ValueError("Unknown catalog IDs: " + ", ".join(unknown))

    replacements: list[tuple[int, int, str]] = []
    for entry_id, translation in batch.items():
        entry = entries[entry_id]
        unresolved = entry["status"] in {"needs_context", "needs_review"}
        replaceable = args.replace_translated and entry["status"] in {"translated", "reviewed"}
        if not unresolved and not replaceable:
            raise ValueError(f"{entry_id} has status {entry['status']!r}, not an unresolved status")
        entry["translation"] = translation
        if args.set_status:
            entry["status"] = args.set_status
        elif unresolved:
            entry["status"] = "translated"
            entry["comment"] = "Primary translation prepared from the module and source label."
            entry.pop("alternatives", None)
        start, end = object_bounds(original, entry_id)
        replacements.append((start, end, json.dumps(entry, ensure_ascii=False, separators=(",", ":"))))

    updated = original
    for start, end, replacement in sorted(replacements, reverse=True):
        updated = updated[:start] + replacement + updated[end:]
    args.catalog.write_text(updated, encoding="utf-8")
    print(f"Promoted entries: {len(replacements)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}")
        raise SystemExit(2)
