#!/usr/bin/env python3
"""Launch Fluent with the project Russian locale without persistent system changes."""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

try:  # Support both `python scripts/launch_fluent.py` and package imports in tests.
    from scripts.check_visual_journal import unsafe_lines
except ModuleNotFoundError:  # pragma: no cover - exercised by the direct CLI smoke test.
    from check_visual_journal import unsafe_lines


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


def fluent_command(launcher: Path, fluent_args: list[str], journal: Path | None = None) -> list[str]:
    """Return a Fluent command, optionally replaying a GUI-only QA journal."""
    command = [str(launcher), *fluent_args]
    if journal is not None:
        command.extend(("-i", str(journal)))
    return command


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Запуск Fluent с русскими Qt-каталогами через lang=ru"
    )
    parser.add_argument("--fluent-root", type=Path, required=True, help="Каталог <release>/fluent")
    parser.add_argument("--dry-run", action="store_true", help="Показать команду без запуска")
    parser.add_argument("--wait", action="store_true", help="Ждать завершения Fluent")
    parser.add_argument(
        "--capture-output", type=Path,
        help="Локальный каталог для автоматических кадров visual QA; запускает наблюдатель окна Fluent",
    )
    parser.add_argument(
        "--journal", type=Path,
        help="Fluent journal для воспроизводимой навигации; добавляется как аргумент -i",
    )
    parser.add_argument("fluent_args", nargs=argparse.REMAINDER, help="Аргументы после --")
    args = parser.parse_args()

    fluent_root = args.fluent_root.resolve()
    if not fluent_root.is_dir():
        raise ValueError(f"Каталог Fluent не найден: {fluent_root}")
    launcher = find_launcher(fluent_root)
    fluent_args = list(args.fluent_args)
    if fluent_args and fluent_args[0] == "--":
        fluent_args.pop(0)
    journal = args.journal.resolve() if args.journal else None
    if journal is not None and not journal.is_file():
        raise ValueError(f"Journal Fluent не найден: {journal}")
    if journal is not None:
        violations = unsafe_lines(journal.read_text(encoding="utf-8"))
        if violations:
            line, content = violations[0]
            raise ValueError(f"Journal visual QA содержит недопустимую строку {line}: {content}")
    command = fluent_command(launcher, fluent_args, journal)
    print("Переменная процесса: lang=ru")
    print("Команда:", shlex.join(command))
    if args.dry_run:
        return 0

    watcher = None
    if args.capture_output:
        capture_script = Path(__file__).with_name("capture_fluent_window.py")
        capture_command = [
            sys.executable, str(capture_script), "--watch", "--exit-when-closed",
            "--output-dir", str(args.capture_output.resolve()),
        ]
        watcher = subprocess.Popen(capture_command, env=localized_environment())
        print(f"Наблюдатель visual QA запущен, PID {watcher.pid}")
    process = subprocess.Popen(command, env=localized_environment())
    print(f"Fluent запущен, PID {process.pid}")
    return process.wait() if args.wait else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        raise SystemExit(2)
