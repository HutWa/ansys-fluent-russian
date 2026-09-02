#!/usr/bin/env python3
"""Safely install project-built Russian QM catalogs into Fluent."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
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


def find_core_directory(fluent_root: Path) -> Path:
    candidates = sorted(path for path in fluent_root.glob("fluent[0-9]*") if path.is_dir())
    if len(candidates) != 1:
        raise ValueError(f"Не удалось однозначно определить ядро Fluent в {fluent_root}")
    return candidates[0]


def atomic_copy(source: Path, target: Path) -> None:
    temporary = target.with_name(target.name + ".afrloc.tmp")
    shutil.copy2(source, temporary)
    temporary.replace(target)


def load_build(staging: Path) -> tuple[dict[str, object], list[tuple[Path, str, str]]]:
    manifest_path = staging / "build-manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("format_version") != 1 or data.get("locale") != "ru":
        raise ValueError("Неподдерживаемый build-manifest.json")
    modules = data.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ValueError("Манифест сборки не содержит модулей.")
    files: list[tuple[Path, str, str]] = []
    for item in modules:
        if not isinstance(item, dict):
            raise ValueError("Некорректная запись модуля в манифесте.")
        name, expected = item.get("file"), item.get("sha256")
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".qm"):
            raise ValueError(f"Недопустимое имя файла в манифесте: {name!r}")
        if not isinstance(expected, str) or len(expected) != 64:
            raise ValueError(f"Некорректный SHA-256 для {name}")
        source = (staging / name).resolve()
        if not inside(staging, source) or not source.is_file() or sha256(source) != expected:
            raise ValueError(f"Собранный файл отсутствует или повреждён: {name}")
        files.append((source, name, expected))
    return data, files


def main() -> int:
    parser = argparse.ArgumentParser(description="Безопасная установка русификации Fluent")
    parser.add_argument("--fluent-root", type=Path, required=True, help="Каталог <release>/fluent")
    parser.add_argument("--staging-dir", type=Path, required=True, help="Результат build_translation.py")
    parser.add_argument("--backup-dir", type=Path, help="Новый или пустой каталог манифеста и резервных копий")
    parser.add_argument("--apply", action="store_true", help="Выполнить изменения; без флага только dry-run")
    args = parser.parse_args()

    fluent_root, staging = args.fluent_root.resolve(), args.staging_dir.resolve()
    if not fluent_root.is_dir() or not staging.is_dir():
        raise ValueError("Каталоги Fluent и staging должны существовать.")
    build, files = load_build(staging)
    core = find_core_directory(fluent_root)
    target_root = (core / "cortex" / "resources" / "language" / "ru").resolve()
    if not inside(fluent_root, target_root):
        raise ValueError("Целевой каталог вышел за пределы установки Fluent.")
    if args.apply and not args.backup_dir:
        raise ValueError("Для установки обязателен --backup-dir.")
    backup = args.backup_dir.resolve() if args.backup_dir else None
    if backup and inside(fluent_root, backup):
        raise ValueError("Резервную копию нельзя хранить внутри установки Fluent.")
    if backup and backup.exists() and any(backup.iterdir()):
        raise ValueError(f"Каталог резервной копии должен быть пустым: {backup}")

    print("Режим:", "установка" if args.apply else "dry-run")
    for _, name, _ in files:
        target = target_root / name
        action = "замена с резервной копией" if target.exists() else "новый файл"
        print(f"{name} -> {target} ({action})")
    if not args.apply:
        return 0

    assert backup is not None
    backup.mkdir(parents=True, exist_ok=True)
    created_locale_directory = not target_root.exists()
    target_root.mkdir(parents=True, exist_ok=True)
    installed: list[dict[str, object]] = []
    try:
        for source, name, expected in files:
            target = target_root / name
            entry: dict[str, object] = {
                "target": str(target.relative_to(fluent_root)),
                "installed_sha256": expected,
                "operation": "replaced" if target.exists() else "created",
            }
            if target.exists():
                backup_file = backup / "originals" / name
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup_file)
                entry["backup"] = str(backup_file.relative_to(backup))
                entry["backup_sha256"] = sha256(backup_file)
            installed.append(entry)
            atomic_copy(source, target)
            if sha256(target) != expected:
                raise OSError(f"Контрольная сумма после установки не совпала: {target}")
        install_manifest = {
            "format_version": 1,
            "fluent_root": str(fluent_root),
            "fluent_version": build.get("fluent_version"),
            "locale": "ru",
            "created_locale_directory": created_locale_directory,
            "files": installed,
        }
        manifest_path = backup / "install-manifest.json"
        manifest_path.write_text(json.dumps(install_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        for entry in reversed(installed):
            target = fluent_root / str(entry["target"])
            if entry["operation"] == "created":
                if target.is_file():
                    target.unlink()
            else:
                original = backup / str(entry["backup"])
                if original.is_file() and sha256(original) == entry["backup_sha256"]:
                    atomic_copy(original, target)
        if created_locale_directory and target_root.is_dir() and not any(target_root.iterdir()):
            target_root.rmdir()
        raise
    print(f"Установка завершена. Манифест отката: {backup / 'install-manifest.json'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        raise SystemExit(2)
