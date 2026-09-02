#!/usr/bin/env python3
"""Safely apply community-authored localization files listed in manifest.json.

The script never discovers or copies proprietary resources into the repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inside(root: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def load_manifest(translation_dir: Path) -> list[dict[str, str]]:
    manifest_path = translation_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Не найден манифест перевода: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = data.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("manifest.json должен содержать непустой массив files.")
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("source"), str) or not isinstance(item.get("target"), str):
            raise ValueError("Каждый элемент files должен содержать строки source и target.")
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Безопасная установка русификации Fluent")
    parser.add_argument("--fluent-root", type=Path, required=True, help="Корень локальной установки Fluent")
    parser.add_argument("--translation-dir", type=Path, required=True, help="Каталог перевода конкретной версии")
    parser.add_argument("--backup-dir", type=Path, help="Каталог резервной копии (по умолчанию рядом с переводом)")
    parser.add_argument("--apply", action="store_true", help="Выполнить изменения; без флага доступен только dry-run")
    args = parser.parse_args()

    root, translations = args.fluent_root.resolve(), args.translation_dir.resolve()
    if not root.is_dir() or not translations.is_dir():
        raise ValueError("Корень Fluent и каталог перевода должны существовать.")
    files = load_manifest(translations)
    backup = (args.backup_dir or translations / ".local-backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")).resolve()
    plan: list[tuple[Path, Path, Path]] = []
    for item in files:
        source = (translations / item["source"]).resolve()
        target = (root / item["target"]).resolve()
        if not inside(translations, source) or not inside(root, target):
            raise ValueError("Манифест содержит путь за пределами допустимого каталога.")
        if not source.is_file() or not target.is_file():
            raise ValueError(f"Не найден исходный или целевой файл: {source} -> {target}")
        plan.append((source, target, backup / item["target"]))

    print("Режим:", "установка" if args.apply else "dry-run")
    for source, target, backup_file in plan:
        print(f"{source.relative_to(translations)} -> {target} (backup: {backup_file})")
    if not args.apply:
        return 0

    manifest: list[dict[str, str]] = []
    try:
        for source, target, backup_file in plan:
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup_file)
            temporary = target.with_name(target.name + ".afrloc.tmp")
            shutil.copy2(source, temporary)
            temporary.replace(target)
            manifest.append({"target": str(target.relative_to(root)), "backup": str(backup_file.relative_to(backup)), "backup_sha256": sha256(backup_file)})
        (backup / "install-manifest.json").write_text(json.dumps({"fluent_root": str(root), "files": manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # Roll back only files already backed up by this run.
        for entry in reversed(manifest):
            original = backup / entry["backup"]
            target = root / entry["target"]
            if original.is_file() and sha256(original) == entry["backup_sha256"]:
                shutil.copy2(original, target)
        raise
    print(f"Установка завершена. Резервная копия: {backup}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        raise SystemExit(2)
