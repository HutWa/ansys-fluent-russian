#!/usr/bin/env python3
"""Basic integrity checks for community translation files (JSON/XML/Qt TS)."""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as etree
from pathlib import Path

TOKEN = re.compile(r"%(?:\d+|[sdf])|\{\d+\}|\\[nt]|</?[^>]+>|&&?|&[A-Za-z]+;")


def check_json(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"{path}: некорректный JSON: {error}"]
    errors: list[str] = []
    if isinstance(data, dict):
        for source, target in data.items():
            if isinstance(source, str) and isinstance(target, str):
                if not target.strip(): errors.append(f"{path}: пустой перевод для {source!r}")
                if sorted(TOKEN.findall(source)) != sorted(TOKEN.findall(target)):
                    errors.append(f"{path}: placeholders/tags отличаются: {source!r}")
    return errors


def check_xml(path: Path) -> list[str]:
    try:
        etree.parse(path)
    except (OSError, etree.ParseError) as error:
        return [f"{path}: некорректный XML/TS: {error}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    for path in args.directory.rglob("*"):
        if path.suffix.lower() == ".json": errors.extend(check_json(path))
        elif path.suffix.lower() in {".xml", ".ts"}: errors.extend(check_xml(path))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Проверка пройдена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
