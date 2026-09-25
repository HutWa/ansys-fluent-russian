#!/usr/bin/env python3
"""Verify that every QM file in a built Fluent package is installed intact."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from scripts.install import find_core_directory, load_build, sha256
except ModuleNotFoundError:  # pragma: no cover - direct CLI execution.
    from install import find_core_directory, load_build, sha256


def verify(fluent_root: Path, staging_dir: Path) -> list[str]:
    """Return a concise mismatch per missing or altered installed QM file."""
    fluent_root = fluent_root.resolve()
    _, built = load_build(staging_dir.resolve())
    language_dir = find_core_directory(fluent_root) / "cortex" / "resources" / "language" / "ru"
    problems: list[str] = []
    for _, name, expected in built:
        target = language_dir / name
        if not target.is_file():
            problems.append(f"missing: {target}")
        elif sha256(target) != expected:
            problems.append(f"checksum mismatch: {target}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify installed Fluent Russian QM catalogs")
    parser.add_argument("--fluent-root", type=Path, required=True, help="Fluent installation directory")
    parser.add_argument("--staging-dir", type=Path, required=True, help="Build output with build-manifest.json")
    args = parser.parse_args()
    try:
        _, built = load_build(args.staging_dir.resolve())
        problems = verify(args.fluent_root, args.staging_dir)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    if problems:
        print(f"Installation verification failed: {len(problems)} of {len(built)} Qt modules differ.")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print(f"Installation verified: {len(built)} Qt modules match the build manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
