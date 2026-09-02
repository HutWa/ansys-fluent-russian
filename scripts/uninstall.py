#!/usr/bin/env python3
"""Restore or remove files recorded by the safe Fluent installer."""
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


def atomic_copy(source: Path, target: Path) -> None:
    temporary = target.with_name(target.name + ".afrloc.tmp")
    shutil.copy2(source, temporary)
    temporary.replace(target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Откат русификации Fluent")
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Выполнить откат; без флага только dry-run")
    args = parser.parse_args()

    backup = args.backup_dir.resolve()
    data = json.loads((backup / "install-manifest.json").read_text(encoding="utf-8"))
    if data.get("format_version") != 1 or data.get("locale") != "ru":
        raise ValueError("Неподдерживаемый install-manifest.json")
    fluent_root = Path(data["fluent_root"]).resolve()
    if not fluent_root.is_dir():
        raise ValueError("Корень Fluent из манифеста недоступен.")
    plan: list[tuple[dict[str, object], Path, Path | None]] = []
    for entry in data.get("files", []):
        target = (fluent_root / str(entry["target"])).resolve()
        if not inside(fluent_root, target) or not target.is_file():
            raise ValueError(f"Установленный файл отсутствует или путь недопустим: {target}")
        if sha256(target) != entry.get("installed_sha256"):
            raise ValueError(f"Установленный файл был изменён; автоматический откат остановлен: {target}")
        original: Path | None = None
        if entry.get("operation") == "replaced":
            original = (backup / str(entry["backup"])).resolve()
            if not inside(backup, original) or not original.is_file():
                raise ValueError(f"Резервная копия отсутствует: {original}")
            if sha256(original) != entry.get("backup_sha256"):
                raise ValueError(f"Резервная копия повреждена: {original}")
        elif entry.get("operation") != "created":
            raise ValueError("Неизвестная операция в манифесте отката.")
        plan.append((entry, target, original))

    print("Режим:", "откат" if args.apply else "dry-run")
    for entry, target, _ in plan:
        action = "восстановить оригинал" if entry["operation"] == "replaced" else "удалить созданный файл"
        print(f"{target} ({action})")
    if not args.apply:
        return 0
    for entry, target, original in reversed(plan):
        if entry["operation"] == "replaced":
            assert original is not None
            atomic_copy(original, target)
        else:
            target.unlink()
    if data.get("created_locale_directory") and plan:
        locale_directory = plan[0][1].parent
        if inside(fluent_root, locale_directory) and locale_directory.is_dir() and not any(locale_directory.iterdir()):
            locale_directory.rmdir()
    print("Откат завершён. Резервная копия и манифест сохранены для аудита.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError, TypeError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        raise SystemExit(2)
