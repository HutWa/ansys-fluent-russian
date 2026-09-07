#!/usr/bin/env python3
"""Report Fluent localization progress from the project catalog.

The inventory contains counts only, never proprietary Fluent source strings, so
the report can run in GitHub Actions without an Ansys installation.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATUSES = {"translated", "reviewed", "needs_context", "needs_review", "do_not_translate"}


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def load_catalog(path: Path) -> dict[str, Any]:
    data = read_json(path)
    entries = data.get("entries")
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise ValueError(f"Catalog has no valid entries array: {path}")
    unknown = sorted({entry.get("status") for entry in entries} - STATUSES)
    if unknown:
        raise ValueError(f"Catalog has unknown statuses: {', '.join(map(str, unknown))}")
    return data


def load_inventory(path: Path) -> dict[str, Any]:
    data = read_json(path)
    total = data.get("total_messages")
    modules = data.get("module_messages")
    if not isinstance(total, int) or total <= 0:
        raise ValueError(f"Inventory total_messages must be a positive integer: {path}")
    if not isinstance(modules, dict) or not all(isinstance(name, str) and isinstance(count, int) and count >= 0 for name, count in modules.items()):
        raise ValueError(f"Inventory module_messages must map names to non-negative integers: {path}")
    return data


def metrics(catalog: dict[str, Any], inventory: dict[str, Any]) -> dict[str, int]:
    statuses = Counter(str(entry["status"]) for entry in catalog["entries"])
    total = int(inventory["total_messages"])
    catalogued = len(catalog["entries"])
    if catalogued > total:
        raise ValueError("Catalog has more entries than the full Fluent inventory")
    translated = statuses["translated"] + statuses["reviewed"]
    return {
        "total": total,
        "catalogued": catalogued,
        "translated": translated,
        "reviewed": statuses["reviewed"],
        "needs_review": statuses["needs_review"],
        "needs_context": statuses["needs_context"],
        "do_not_translate": statuses["do_not_translate"],
        "not_catalogued": total - catalogued,
    }


def percent(numerator: int, denominator: int) -> str:
    return f"{100 * numerator / denominator:.1f}%" if denominator else "n/a"


def module_rows(catalog: dict[str, Any], inventory: dict[str, Any]) -> list[dict[str, Any]]:
    totals = inventory["module_messages"]
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for entry in catalog["entries"]:
        grouped[str(entry["module"])][str(entry["status"])] += 1
    rows: list[dict[str, Any]] = []
    for module, status_counts in grouped.items():
        total = totals.get(module)
        if total is None:
            continue
        translated = status_counts["translated"] + status_counts["reviewed"]
        rows.append({
            "module": module,
            "total": total,
            "catalogued": sum(status_counts.values()),
            "translated": translated,
            "percent": 100 * translated / total if total else 0.0,
        })
    return sorted(rows, key=lambda row: (-row["catalogued"], row["module"].casefold()))


def load_catalog_at_ref(reference: str, catalog_path: Path) -> dict[str, Any]:
    relative = catalog_path.resolve().relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "show", f"{reference}:{relative}"], cwd=ROOT, capture_output=True
    )
    if result.returncode:
        raise ValueError(f"Cannot read {relative} at {reference}: {result.stderr.decode('utf-8', errors='replace').strip()}")
    data = json.loads(result.stdout.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Catalog at {reference} is invalid")
    return data


def delta_markdown(before: dict[str, int], after: dict[str, int]) -> list[str]:
    lines = ["", "### Change in this revision", "", "| Metric | Before | After | Change |", "|---|---:|---:|---:|"]
    for key, label in (("translated", "Translated"), ("needs_review", "Needs review"), ("needs_context", "Needs context")):
        change = after[key] - before[key]
        lines.append(f"| {label} | {before[key]:,} | {after[key]:,} | {change:+,} |")
    lines.extend([
        "",
        f"Overall translated: {percent(before['translated'], before['total'])} -> {percent(after['translated'], after['total'])}",
    ])
    return lines


def render_markdown(
    current: dict[str, int], rows: list[dict[str, Any]], module_names: list[str], show_all_modules: bool,
    before: dict[str, int] | None = None,
) -> str:
    lines = [
        "## Fluent 2026 R1 localization",
        "",
        "| Status | Strings |",
        "|---|---:|",
        f"| Translated | **{current['translated']:,}** |",
        f"| Needs review | {current['needs_review']:,} |",
        f"| Needs context | {current['needs_context']:,} |",
        f"| Do not translate | {current['do_not_translate']:,} |",
        f"| Not catalogued | {current['not_catalogued']:,} |",
        "",
        f"**Overall translated:** {current['translated']:,} / {current['total']:,} ({percent(current['translated'], current['total'])})  ",
        f"**Catalogued / classified:** {current['catalogued']:,} / {current['total']:,} ({percent(current['catalogued'], current['total'])})",
    ]
    if before is not None:
        lines.extend(delta_markdown(before, current))

    by_name = {row["module"]: row for row in rows}
    selected = [by_name[name] for name in module_names if name in by_name]
    if show_all_modules:
        selected = rows
    elif not selected:
        selected = rows[:15]
    if selected:
        lines.extend(["", "### Module coverage", "", "| Module | Translated | Catalogued | Total | Coverage |", "|---|---:|---:|---:|---:|"])
        for row in selected:
            lines.append(f"| {row['module']} | {row['translated']:,} | {row['catalogued']:,} | {row['total']:,} | {row['percent']:.1f}% |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Report Fluent translation progress")
    parser.add_argument("--catalog", type=Path, default=ROOT / "translations" / "v2026R1" / "catalog.json")
    parser.add_argument("--inventory", type=Path, default=ROOT / "profiles" / "v2026R1_inventory.json")
    parser.add_argument("--base-ref", help="Git ref used for a before/after delta")
    parser.add_argument("--module", action="append", default=[], help="Module to show; repeat as needed")
    parser.add_argument("--all-modules", action="store_true", help="Show every catalogued module")
    parser.add_argument("--github-summary", action="store_true", help="Append Markdown to GITHUB_STEP_SUMMARY")
    args = parser.parse_args()
    try:
        inventory = load_inventory(args.inventory)
        catalog = load_catalog(args.catalog)
        current = metrics(catalog, inventory)
        before = metrics(load_catalog_at_ref(args.base_ref, args.catalog), inventory) if args.base_ref else None
        report = render_markdown(current, module_rows(catalog, inventory), args.module, args.all_modules, before)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(report, end="")
    if args.github_summary:
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if not summary:
            print("Warning: GITHUB_STEP_SUMMARY is not set; report was printed only.", file=sys.stderr)
        else:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
