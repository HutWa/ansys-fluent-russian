#!/usr/bin/env python3
"""Restore originals from an install-manifest.json created by install.py."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Откат русификации Fluent")
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Выполнить восстановление; иначе dry-run")
    args = parser.parse_args()
    backup = args.backup_dir.resolve()
    data = json.loads((backup / "install-manifest.json").read_text(encoding="utf-8"))
    root = Path(data["fluent_root"]).resolve()
    if not root.is_dir():
        raise ValueError("Корень Fluent из манифеста недоступен.")
    plan = []
    for item in data.get("files", []):
        original, target = (backup / item["backup"]).resolve(), (root / item["target"]).resolve()
        if not original.is_file() or digest(original) != item["backup_sha256"]:
            raise ValueError(f"Повреждена резервная копия: {original}")
        try:
            target.relative_to(root)
        except ValueError:
            raise ValueError("Недопустимый целевой путь в манифесте.")
        plan.append((original, target))
    print("Режим:", "восстановление" if args.apply else "dry-run")
    for original, target in plan:
        print(f"{original} -> {target}")
    if args.apply:
        for original, target in plan:
            shutil.copy2(original, target)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        raise SystemExit(2)
