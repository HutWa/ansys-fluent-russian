#!/usr/bin/env python3
"""Extract selected Qt translation modules from a local Fluent installation.

The generated *.extracted.json file is local working data and must not be
committed. Raw TS files are created only inside a temporary directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as etree
from pathlib import Path


def find_core_directory(fluent_root: Path) -> Path:
    candidates = sorted(path for path in fluent_root.glob("fluent[0-9]*") if path.is_dir())
    if len(candidates) != 1:
        raise ValueError(
            f"Ожидался один каталог fluent<version> в {fluent_root}, найдено: {len(candidates)}"
        )
    return candidates[0]


def find_lconvert(fluent_root: Path, explicit: Path | None) -> Path:
    if explicit:
        tool = explicit.resolve()
        if not tool.is_file():
            raise ValueError(f"lconvert не найден: {tool}")
        return tool
    release_root = fluent_root.parent
    candidate = release_root / "tp" / "qt" / "5.15.19" / "winx64" / "bin" / "lconvert.exe"
    if candidate.is_file():
        return candidate
    discovered = sorted(release_root.rglob("lconvert.exe"))
    if not discovered:
        raise ValueError("В установке не найден lconvert.exe; укажите --lconvert.")
    return discovered[0]


def message_id(module: str, context: str, source: str, comment: str) -> str:
    value = "\0".join((module, context, source, comment)).encode("utf-8")
    return f"{module}:{hashlib.sha256(value).hexdigest()[:16]}"


def parse_ts(path: Path, module: str) -> list[dict[str, str]]:
    root = etree.parse(path).getroot()
    strings: list[dict[str, str]] = []
    for context_node in root.findall("context"):
        context = context_node.findtext("name", default="")
        for message in context_node.findall("message"):
            source = message.findtext("source", default="")
            if not source:
                continue
            comment = message.findtext("comment", default="")
            strings.append(
                {
                    "id": message_id(module, context, source, comment),
                    "module": module,
                    "context": context,
                    "source": source,
                    "comment": comment,
                    "reference_translation": message.findtext("translation", default=""),
                }
            )
    return strings


def convert_module(lconvert: Path, source: Path, temporary_root: Path) -> list[dict[str, str]]:
    output = temporary_root / f"{source.stem}.ts"
    subprocess.run(
        [str(lconvert), "-i", str(source), "-o", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_ts(output, source.stem)


def main() -> int:
    parser = argparse.ArgumentParser(description="Локальное извлечение UI-строк Fluent по модулям")
    parser.add_argument("--fluent-root", type=Path, required=True, help="Каталог <release>/fluent")
    parser.add_argument("--reference-locale", default="ja", help="Штатный каталог-источник, по умолчанию ja")
    parser.add_argument("--lconvert", type=Path, help="Явный путь к Qt lconvert.exe")
    parser.add_argument("--list-modules", action="store_true", help="Показать доступные модули и завершить работу")
    parser.add_argument("--module", action="append", default=[], help="Имя модуля без .qm; можно повторять")
    parser.add_argument("--output", type=Path, help="Локальный файл с окончанием .extracted.json")
    args = parser.parse_args()

    fluent_root = args.fluent_root.resolve()
    if not fluent_root.is_dir():
        raise ValueError(f"Каталог Fluent не найден: {fluent_root}")
    core = find_core_directory(fluent_root)
    locale_root = core / "cortex" / "resources" / "language" / args.reference_locale
    if not locale_root.is_dir():
        raise ValueError(f"Штатный языковой каталог не найден: {locale_root}")
    available = {path.stem: path for path in locale_root.glob("*.qm")}

    if args.list_modules:
        for name in sorted(available, key=str.casefold):
            print(f"{name}\t{available[name].stat().st_size}")
        print(f"Всего модулей: {len(available)}", file=sys.stderr)
        return 0
    if not args.module:
        raise ValueError("Для безопасной блочной работы укажите хотя бы один --module.")
    if not args.output or not args.output.name.endswith(".extracted.json"):
        raise ValueError("--output должен оканчиваться на .extracted.json")
    output = args.output.resolve()
    if not output.parent.is_dir():
        raise ValueError(f"Родительский каталог результата не существует: {output.parent}")
    unknown = sorted(set(args.module) - available.keys())
    if unknown:
        raise ValueError(f"Неизвестные модули: {', '.join(unknown)}")

    lconvert = find_lconvert(fluent_root, args.lconvert)
    strings: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="afrloc-") as temporary:
        temporary_root = Path(temporary)
        for module in args.module:
            strings.extend(convert_module(lconvert, available[module], temporary_root))
    payload = {
        "format_version": 1,
        "fluent_version": core.name.removeprefix("fluent"),
        "source_locale": "en",
        "reference_locale": args.reference_locale,
        "modules": args.module,
        "strings": strings,
    }
    temporary_output = output.with_name(output.name + ".tmp")
    temporary_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_output.replace(output)
    print(f"Извлечено строк: {len(strings)}. Локальный файл: {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, etree.ParseError, subprocess.CalledProcessError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        raise SystemExit(2)
