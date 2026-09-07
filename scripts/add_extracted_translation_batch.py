#!/usr/bin/env python3
"""Add selected translations from an extracted Fluent module without reformatting.

The batch maps stable extracted IDs to human-authored Russian UI text.  The
extract file is intentionally local working data; only the selected catalog
entries are written to the repository catalog.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def array_end(text: str, key: str) -> int:
    """Find the closing bracket for a top-level JSON array property."""
    key_at = text.find(json.dumps(key))
    if key_at < 0:
        raise ValueError(f"JSON key not found: {key}")
    start = text.find("[", key_at)
    if start < 0:
        raise ValueError(f"Array start not found: {key}")
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"Array end not found: {key}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Add selected extracted Fluent translations")
    parser.add_argument("catalog", type=Path)
    parser.add_argument("extracted", type=Path)
    parser.add_argument("batch", type=Path)
    args = parser.parse_args()

    raw_catalog = args.catalog.read_text(encoding="utf-8")
    catalog = json.loads(raw_catalog)
    extracted = json.loads(args.extracted.read_text(encoding="utf-8"))
    batch = json.loads(args.batch.read_text(encoding="utf-8"))
    if not isinstance(batch, dict) or not all(isinstance(key, str) and isinstance(value, str) and value.strip() for key, value in batch.items()):
        raise ValueError("The batch must map extracted IDs to non-empty translations.")

    existing_ids = {entry["id"] for entry in catalog["entries"]}
    sources = {item["id"]: item for item in extracted.get("strings", [])}
    unknown = sorted(set(batch) - set(sources))
    duplicates = sorted(set(batch) & existing_ids)
    if unknown:
        raise ValueError("Unknown extracted IDs: " + ", ".join(unknown))
    if duplicates:
        raise ValueError("Catalog IDs already exist: " + ", ".join(duplicates))

    additions = []
    for entry_id, translation in batch.items():
        source = sources[entry_id]
        additions.append(
            {
                "id": entry_id,
                "module": source["module"],
                "qt_context": source["context"],
                "source": source["source"],
                "translation": translation,
                "status": "translated",
                "context": f"{source['module']} / {source['context']}; UI label imported from the Fluent reference module.",
                "comment": "Primary translation prepared from the module and source label.",
            }
        )

    end = array_end(raw_catalog, "entries")
    prefix = ",\n" if catalog["entries"] else ""
    rendered = ",\n".join(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) for entry in additions)
    updated = raw_catalog[:end].rstrip() + prefix + rendered + "\n  " + raw_catalog[end:]
    args.catalog.write_text(updated, encoding="utf-8")
    print(f"Added entries: {len(additions)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, KeyError) as error:
        print(f"Error: {error}")
        raise SystemExit(2)
