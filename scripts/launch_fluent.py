#!/usr/bin/env python3
"""Launch Fluent with the project Russian locale without persistent system changes."""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


def find_launcher(fluent_root: Path) -> Path:
    candidates = (
        fluent_root / "ntbin" / "win64" / "fluent.exe",
        fluent_root / "bin" / "fluent",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ValueError(f"Не найден исполняемый файл Fluent в {fluent_root}")


def localized_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["lang"] = "ru"
    return environment


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Запуск Fluent с русскими Qt-каталогами через lang=ru"
    )
    parser.add_argument("--fluent-root", type=Path, required=True, help="Каталог <release>/fluent")
    parser.add_argument("--dry-run", action="store_true", help="Показать команду без запуска")
    parser.add_argument("--wait", action="store_true", help="Ждать завершения Fluent")
    parser.add_argument("fluent_args", nargs=argparse.REMAINDER, help="Аргументы после --")
    args = parser.parse_args()

    fluent_root = args.fluent_root.resolve()
    if not fluent_root.is_dir():
        raise ValueError(f"Каталог Fluent не найден: {fluent_root}")
    launcher = find_launcher(fluent_root)
    fluent_args = list(args.fluent_args)
    if fluent_args and fluent_args[0] == "--":
        fluent_args.pop(0)
    command = [str(launcher), *fluent_args]
    print("Переменная процесса: lang=ru")
    print("Команда:", shlex.join(command))
    if args.dry_run:
        return 0

    process = subprocess.Popen(command, env=localized_environment())
    print(f"Fluent запущен, PID {process.pid}")
    return process.wait() if args.wait else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        raise SystemExit(2)
