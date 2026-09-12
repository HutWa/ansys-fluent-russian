#!/usr/bin/env python3
"""Launch Fluent on an isolated copy of a case for visual QA only.

The bootstrap journal contains exactly one Fluent action: ``/file/read-case``.
It never writes, initializes, solves, or changes the source case.  GUI routes
are deliberately kept in separate scripts and may only navigate visible UI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from scripts.launch_fluent import find_launcher, localized_environment
except ModuleNotFoundError:  # pragma: no cover - exercised by direct CLI use.
    from launch_fluent import find_launcher, localized_environment


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_only_journal(case_copy: Path) -> str:
    """Return the only permitted non-GUI bootstrap action."""
    return "; Visual QA read-only bootstrap\n/file/read-case \"%s\"\n" % case_copy.as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Fluent on an isolated read-only case copy")
    parser.add_argument("--fluent-root", type=Path, required=True)
    parser.add_argument("--source-case", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = args.source_case.resolve()
    fluent_root = args.fluent_root.resolve()
    output = args.output_dir.resolve()
    if not source.is_file():
        raise ValueError(f"Case file not found: {source}")
    launcher = find_launcher(fluent_root)
    output.mkdir(parents=True, exist_ok=True)
    case_copy = output / source.name
    journal = output / "read-only-bootstrap.jou"
    metadata = output / "read-only-bootstrap.json"
    if args.dry_run:
        print(read_only_journal(case_copy), end="")
        return 0

    shutil.copy2(source, case_copy)
    source_digest, copy_digest = file_hash(source), file_hash(case_copy)
    if source_digest != copy_digest:
        raise ValueError("Copied case checksum does not match source")
    journal.write_text(read_only_journal(case_copy), encoding="utf-8")
    command = [str(launcher), "3d", "-t1", "-i", str(journal)]
    metadata.write_text(json.dumps({
        "source_case": str(source), "source_sha256": source_digest,
        "case_copy": str(case_copy), "copy_sha256": copy_digest,
        "journal": str(journal), "command": command,
        "guarantees": ["source case is copied before Fluent starts", "bootstrap contains only /file/read-case", "no save or solver command"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    capture_script = Path(__file__).with_name("capture_fluent_window.py")
    watcher_log = output / "watcher.log"
    with watcher_log.open("a", encoding="utf-8") as log:
        watcher = subprocess.Popen([
            sys.executable, str(capture_script), "--watch", "--exit-when-closed", "--output-dir", str(output),
        ], env=localized_environment(), stdout=log, stderr=subprocess.STDOUT)
    process = subprocess.Popen(command, env=localized_environment())
    print(f"Read-only visual-QA watcher PID {watcher.pid}")
    print(f"Fluent PID {process.pid}; source checksum verified before launch")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"Read-only visual-QA launch error: {error}", file=sys.stderr)
        raise SystemExit(2)
