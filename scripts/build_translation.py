#!/usr/bin/env python3
"""Build project-authored Russian Qt catalogs in a staging directory."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as etree
from collections import defaultdict
from pathlib import Path

try:
    from scripts.validate_translation import check_catalog
except ModuleNotFoundError:
    from validate_translation import check_catalog


def inside(root: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def find_lrelease(fluent_root: Path, explicit: Path | None) -> Path:
    if explicit:
        tool = explicit.resolve()
        if not tool.is_file():
            raise ValueError(f"lrelease не найден: {tool}")
        return tool
    release_root = fluent_root.resolve().parent
    candidate = release_root / "tp" / "qt" / "5.15.19" / "winx64" / "bin" / "lrelease.exe"
    if candidate.is_file():
        return candidate
    discovered = sorted(release_root.rglob("lrelease.exe"))
    if not discovered:
        raise ValueError("В установке не найден lrelease.exe; укажите --lrelease.")
    return discovered[0]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_ts(entries: list[dict[str, object]], output: Path) -> int:
    root = etree.Element("TS", {"version": "2.1", "language": "ru"})
    contexts: dict[str, list[dict[str, object]]] = defaultdict(list)
    for entry in entries:
        if entry["status"] in {"needs_context", "do_not_translate"} or not entry["translation"]:
            continue
        contexts[str(entry["qt_context"])].append(entry)
    count = 0
    for context_name in sorted(contexts, key=str.casefold):
        context_node = etree.SubElement(root, "context")
        etree.SubElement(context_node, "name").text = context_name
        for entry in contexts[context_name]:
            message = etree.SubElement(context_node, "message")
            etree.SubElement(message, "source").text = str(entry["source"])
            if entry.get("comment"):
                etree.SubElement(message, "comment").text = str(entry["comment"])
            etree.SubElement(message, "translation").text = str(entry["translation"])
            count += 1
    etree.indent(root, space="    ")
    tree = etree.ElementTree(root)
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Сборка русских Qt-каталогов Fluent")
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--fluent-root", type=Path, required=True, help="Каталог <release>/fluent")
    parser.add_argument("--output-dir", type=Path, required=True, help="Новый или пустой staging-каталог")
    parser.add_argument("--lrelease", type=Path, help="Явный путь к Qt lrelease.exe")
    args = parser.parse_args()

    fluent_root = args.fluent_root.resolve()
    if not fluent_root.is_dir():
        raise ValueError(f"Каталог Fluent не найден: {fluent_root}")
    output_dir = args.output_dir.resolve()
    if inside(fluent_root, output_dir):
        raise ValueError("Сборка непосредственно внутри установки Fluent запрещена; используйте staging-каталог.")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"Staging-каталог должен быть пустым: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    glossary_path = Path(__file__).resolve().parents[1] / "dictionary" / "glossary_ru.json"
    glossary = json.loads(glossary_path.read_text(encoding="utf-8"))
    errors, warnings = check_catalog(args.catalog, catalog, glossary)
    for warning in warnings:
        print(f"ПРЕДУПРЕЖДЕНИЕ: {warning}", file=sys.stderr)
    if errors:
        raise ValueError("Каталог не прошёл проверку:\n" + "\n".join(errors))

    modules: dict[str, list[dict[str, object]]] = defaultdict(list)
    for entry in catalog["entries"]:
        modules[str(entry["module"])].append(entry)
    lrelease = find_lrelease(fluent_root, args.lrelease)
    built: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="afrloc-build-") as temporary:
        temporary_root = Path(temporary)
        for module in sorted(modules, key=str.casefold):
            source_ts = temporary_root / f"{module}.ts"
            message_count = render_ts(modules[module], source_ts)
            if not message_count:
                continue
            output_qm = output_dir / f"{module}.qm"
            subprocess.run(
                [str(lrelease), str(source_ts), "-qm", str(output_qm)],
                check=True,
                capture_output=True,
                text=True,
            )
            built.append(
                {
                    "module": module,
                    "file": output_qm.name,
                    "messages": message_count,
                    "sha256": sha256(output_qm),
                }
            )
    manifest = {
        "format_version": 1,
        "fluent_version": catalog["fluent_version"],
        "locale": "ru",
        "modules": built,
    }
    (output_dir / "build-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Собрано модулей: {len(built)}. Staging-каталог: {output_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        raise SystemExit(2)
