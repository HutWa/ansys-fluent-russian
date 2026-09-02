#!/usr/bin/env python3
"""Reject files that must not be published in this community repository."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath


MAX_FILE_SIZE = 20 * 1024 * 1024
FORBIDDEN_SUFFIXES = {
    ".7z", ".bin", ".cab", ".dat", ".dll", ".dylib", ".exe", ".iso",
    ".lic", ".lib", ".msi", ".pak", ".rar", ".so", ".zip",
}
FORBIDDEN_PARTS = {"backups", "extracted-resources"}


def tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [root / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def inspect_file(root: Path, path: Path) -> list[str]:
    relative = path.relative_to(root)
    portable = PurePosixPath(relative.as_posix())
    errors: list[str] = []
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        errors.append(f"запрещённый тип файла: {portable}")
    if FORBIDDEN_PARTS.intersection(part.lower() for part in portable.parts):
        errors.append(f"запрещённый каталог: {portable}")
    if path.stat().st_size > MAX_FILE_SIZE:
        errors.append(
            f"файл превышает лимит проекта 20 MiB: {portable} "
            f"({path.stat().st_size / 1024 / 1024:.1f} MiB)"
        )
    with path.open("rb") as stream:
        if stream.read(2) == b"MZ":
            errors.append(f"обнаружен Windows-бинарник, возможно переименованный: {portable}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors: list[str] = []
    try:
        files = tracked_files(root)
        for path in files:
            if path.is_file():
                errors.extend(inspect_file(root, path))
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Ошибка проверки репозитория: {error}", file=sys.stderr)
        return 2
    if errors:
        print("Публикация заблокирована:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Проверено файлов: {len(files)}. Запрещённых материалов не обнаружено.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
