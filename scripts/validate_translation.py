#!/usr/bin/env python3
"""Integrity and workflow checks for community translation files."""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as etree
from datetime import date
from pathlib import Path

TOKEN = re.compile(r"%(?:\d+|[sdf])|\{\d+\}|\\[nt]|</?[^>]+>|&&?|&[A-Za-z]+;")
STATUSES = {"translated", "reviewed", "needs_context", "needs_review", "do_not_translate"}


def tokens(value: str) -> list[str]:
    return sorted(TOKEN.findall(value))


def check_catalog(
    path: Path,
    data: dict[object, object],
    glossary: dict[str, str] | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if data.get("format_version") != 1:
        errors.append(f"{path}: format_version должен быть равен 1")
    if not isinstance(data.get("fluent_version"), str) or not data["fluent_version"].strip():
        errors.append(f"{path}: не указана fluent_version")
    if data.get("source_locale") != "en" or data.get("target_locale") != "ru":
        errors.append(f"{path}: ожидается направление локализации en -> ru")
    entries = data.get("entries")
    if not isinstance(entries, list):
        return errors + [f"{path}: entries должен быть массивом"], warnings

    identifiers: set[str] = set()
    for index, entry in enumerate(entries):
        location = f"{path}: entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{location}: запись должна быть объектом")
            continue
        identifier = entry.get("id")
        source = entry.get("source")
        translation = entry.get("translation")
        status = entry.get("status")
        comment = entry.get("comment", "")
        context = entry.get("context")

        if not isinstance(identifier, str) or not identifier.strip():
            errors.append(f"{location}: отсутствует непустой id")
        elif identifier in identifiers:
            errors.append(f"{location}: повторяющийся id {identifier!r}")
        else:
            identifiers.add(identifier)
        if not isinstance(source, str) or not source.strip():
            errors.append(f"{location}: отсутствует исходная строка")
            continue
        if not isinstance(translation, str):
            errors.append(f"{location}: translation должен быть строкой")
            continue
        if not isinstance(context, str):
            errors.append(f"{location}: context должен быть строкой")
        if status not in STATUSES:
            errors.append(f"{location}: неизвестный статус {status!r}")
            continue
        if status in {"translated", "reviewed", "needs_review"} and not translation.strip():
            errors.append(f"{location}: для статуса {status} нужен перевод")
        if translation and tokens(source) != tokens(translation):
            errors.append(f"{location}: placeholders/tags отличаются")
        if status in {"needs_context", "needs_review"} and (
            not isinstance(comment, str) or not comment.strip()
        ):
            errors.append(f"{location}: сомнение должно быть объяснено в comment")
        if status == "reviewed":
            review = entry.get("review")
            if not isinstance(review, dict) or not all(
                isinstance(review.get(field), str) and review[field].strip()
                for field in ("reviewer", "checked_at")
            ):
                errors.append(f"{location}: reviewed требует review.reviewer и review.checked_at")
            else:
                try:
                    date.fromisoformat(review["checked_at"])
                except ValueError:
                    errors.append(f"{location}: review.checked_at должен иметь формат YYYY-MM-DD")
        alternatives = entry.get("alternatives")
        if alternatives is not None and (
            not isinstance(alternatives, list)
            or not all(isinstance(value, str) and value.strip() for value in alternatives)
        ):
            errors.append(f"{location}: alternatives должен быть массивом непустых строк")
        if glossary and source in glossary and translation and translation != glossary[source]:
            errors.append(
                f"{location}: перевод расходится с глоссарием; ожидается {glossary[source]!r}"
            )
        if translation == source and status != "do_not_translate":
            warnings.append(f"{location}: перевод совпадает с оригиналом")
        if translation and len(source) >= 8 and len(translation) > max(len(source) * 2.2, len(source) + 30):
            warnings.append(f"{location}: перевод подозрительно длиннее оригинала")
    return errors, warnings


def validate_json(
    path: Path, glossary: dict[str, str] | None = None
) -> tuple[list[str], list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"{path}: некорректный JSON: {error}"], []
    if isinstance(data, dict) and "entries" in data:
        return check_catalog(path, data, glossary)
    errors: list[str] = []
    if isinstance(data, dict):
        for source, target in data.items():
            if isinstance(source, str) and isinstance(target, str):
                if not target.strip(): errors.append(f"{path}: пустой перевод для {source!r}")
                if tokens(source) != tokens(target):
                    errors.append(f"{path}: placeholders/tags отличаются: {source!r}")
    return errors, []


def check_json(path: Path) -> list[str]:
    """Compatibility wrapper used by tests and external callers."""
    return validate_json(path)[0]


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
    warnings: list[str] = []
    glossary_path = Path(__file__).resolve().parents[1] / "dictionary" / "glossary_ru.json"
    try:
        glossary = json.loads(glossary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Не удалось загрузить глоссарий: {error}", file=sys.stderr)
        return 2
    if not args.directory.is_dir():
        print(f"Каталог не найден: {args.directory}", file=sys.stderr)
        return 2
    for path in args.directory.rglob("*"):
        if path.suffix.lower() == ".json":
            file_errors, file_warnings = validate_json(path, glossary)
            errors.extend(file_errors)
            warnings.extend(file_warnings)
        elif path.suffix.lower() in {".xml", ".ts"}: errors.extend(check_xml(path))
    for warning in warnings:
        print(f"ПРЕДУПРЕЖДЕНИЕ: {warning}", file=sys.stderr)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Проверка пройдена. Предупреждений: {len(warnings)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
