#!/usr/bin/env python3
"""Create a local inventory of candidate strings; never writes into the repository by default."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Локальный инвентарь ресурсов для ручного анализа")
    parser.add_argument("source", type=Path, help="Файл ресурса из локальной установки Fluent")
    parser.add_argument("--output", type=Path, required=True, help="Локальный путь результата; не коммитить")
    args = parser.parse_args()
    source = args.source.resolve()
    if not source.is_file():
        parser.error("source должен быть существующим файлом")
    # Extraction rules will be added only after the concrete resource format is identified.
    payload = {"source_name": source.name, "format": source.suffix.lower(), "status": "needs_format_adapter", "strings": []}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Создан локальный инвентарь: {args.output}")


if __name__ == "__main__":
    main()
