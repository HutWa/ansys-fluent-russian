#!/usr/bin/env python3
"""Reject Fluent visual-QA journals that contain anything except navigation."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


NAVIGATION = re.compile(
    r'^\(cx-gui-do cx-set-list-tree-selections "[^"]+" \(list "[^"]+"\)\)$'
)
SLEEP = re.compile(r"^\(sleep [1-9][0-9]*(?:\.[0-9]+)?\)$")


def unsafe_lines(text: str) -> list[tuple[int, str]]:
    """Return non-comment journal lines outside the deliberately tiny safe subset."""
    violations: list[tuple[int, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if not NAVIGATION.fullmatch(line) and not SLEEP.fullmatch(line):
            violations.append((number, raw))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a read-only Fluent visual-QA journal")
    parser.add_argument("journal", type=Path)
    args = parser.parse_args()
    violations = unsafe_lines(args.journal.read_text(encoding="utf-8"))
    if not violations:
        print(f"Safe visual-QA journal: {args.journal}")
        return 0
    for number, line in violations:
        print(f"Unsafe journal line {number}: {line}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
