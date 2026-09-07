#!/usr/bin/env python3
"""Validate visual QA metadata and flag verified windows affected by a change."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATUSES = {"unverified", "partial", "verified", "needs_recheck"}


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected an object: {path}")
    return data


def changed_modules(base_ref: str, catalog_path: Path) -> set[str]:
    relative = catalog_path.resolve().relative_to(ROOT).as_posix()
    result = subprocess.run(["git", "show", f"{base_ref}:{relative}"], cwd=ROOT, capture_output=True)
    if result.returncode:
        raise ValueError(f"Cannot read catalog at {base_ref}: {result.stderr.decode('utf-8', errors='replace').strip()}")
    before = json.loads(result.stdout.decode("utf-8"))
    after = read_json(catalog_path)
    before_entries = {entry["id"]: entry for entry in before.get("entries", [])}
    after_entries = {entry["id"]: entry for entry in after.get("entries", [])}
    changed: set[str] = set()
    for identifier in before_entries.keys() | after_entries.keys():
        old, new = before_entries.get(identifier), after_entries.get(identifier)
        if old is None or new is None:
            changed.add(str((old or new)["module"]))
        elif old.get("translation") != new.get("translation") or old.get("status") != new.get("status"):
            changed.add(str(new["module"]))
    return changed


def validate_review(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    windows = data.get("windows")
    if data.get("format_version") != 1 or not isinstance(windows, list):
        return [], ["reviews file must contain format_version 1 and a windows array"]
    ids: set[str] = set()
    for index, window in enumerate(windows):
        location = f"windows[{index}]"
        if not isinstance(window, dict):
            errors.append(f"{location} must be an object")
            continue
        identifier, title, modules, status = window.get("id"), window.get("window"), window.get("modules"), window.get("status")
        if not isinstance(identifier, str) or not identifier:
            errors.append(f"{location} has no id")
        elif identifier in ids:
            errors.append(f"{location} duplicates id {identifier}")
        else:
            ids.add(identifier)
        if not isinstance(title, str) or not title:
            errors.append(f"{location} has no window title")
        if not isinstance(modules, list) or not modules or not all(isinstance(module, str) and module for module in modules):
            errors.append(f"{location} must list one or more modules")
        if status not in STATUSES:
            errors.append(f"{location} has unsupported status {status!r}")
        issues = window.get("issues")
        if not isinstance(issues, list) or not all(isinstance(issue, str) and issue for issue in issues):
            errors.append(f"{location} issues must be an array of non-empty strings")
        if status != "unverified":
            checked = window.get("last_checked")
            if not isinstance(checked, str):
                errors.append(f"{location} needs last_checked")
            else:
                try:
                    date.fromisoformat(checked)
                except ValueError:
                    errors.append(f"{location} last_checked must be YYYY-MM-DD")
            if not isinstance(window.get("package"), str) or not window["package"]:
                errors.append(f"{location} needs package")
            if not isinstance(window.get("scope"), str) or not window["scope"]:
                errors.append(f"{location} needs scope")
        if status == "verified" and issues:
            errors.append(f"{location} is verified but still has issues; use partial or needs_recheck")
    return [window for window in windows if isinstance(window, dict)], errors


def render_summary(windows: list[dict[str, Any]], warnings: list[str]) -> str:
    counts = Counter(str(window.get("status")) for window in windows)
    lines = [
        "## Visual QA",
        "",
        "| Status | Windows |",
        "|---|---:|",
        f"| Verified | {counts['verified']} |",
        f"| Partial | {counts['partial']} |",
        f"| Needs recheck | {counts['needs_recheck']} |",
        f"| Unverified | {counts['unverified']} |",
    ]
    if warnings:
        lines.extend(["", "### Recheck warning", ""])
        lines.extend(f"- ⚠ {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Fluent visual QA metadata")
    parser.add_argument("--reviews", type=Path, default=ROOT / "reviews" / "v2026R1" / "windows.yml")
    parser.add_argument("--catalog", type=Path, default=ROOT / "translations" / "v2026R1" / "catalog.json")
    parser.add_argument("--base-ref", help="Git ref to compare with the current catalog")
    parser.add_argument("--github-summary", action="store_true")
    args = parser.parse_args()
    try:
        windows, errors = validate_review(read_json(args.reviews))
        if errors:
            raise ValueError("\n".join(errors))
        warnings: list[str] = []
        if args.base_ref:
            changed = changed_modules(args.base_ref, args.catalog)
            for window in windows:
                affected = changed.intersection(window["modules"])
                if window["status"] == "verified" and affected:
                    warnings.append(f"{window['window']} is verified, but changed modules require a visual recheck: {', '.join(sorted(affected))}.")
        report = render_summary(windows, warnings)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(report, end="")
    for warning in warnings:
        print(f"::warning title=Visual QA recheck::{warning}")
    if args.github_summary:
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write("\n" + report)
        else:
            print("Warning: GITHUB_STEP_SUMMARY is not set; report was printed only.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
