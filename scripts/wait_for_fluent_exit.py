#!/usr/bin/env python3
"""Start one isolated Fluent visual-QA run after the current Home window closes.

The helper never closes or drives Fluent.  It waits for the named visible
window to be absent, validates the immutable source case hash, and delegates
the actual launch to ``launch_readonly_case.py``.  Each run receives a new
timestamped directory, so neither the source case nor prior QA evidence is
overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.capture_fluent_window import find_windows
except ModuleNotFoundError:  # pragma: no cover - direct script execution.
    from capture_fluent_window import find_windows


ROOT = Path(__file__).resolve().parents[1]


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_directory(output_root: Path, now: datetime | None = None) -> Path:
    now = now or datetime.now(timezone.utc)
    return output_root / f"rerun-{now.strftime('%Y%m%dT%H%M%SZ')}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch an isolated Fluent QA rerun after Home closes")
    parser.add_argument("--fluent-root", type=Path, required=True)
    parser.add_argument("--source-case", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True, help="Expected SHA-256 of the original source case")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--title-contains", default="Fluent@Home")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=float, default=14400.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.poll_seconds <= 0 or args.timeout_seconds <= 0:
        parser.error("--poll-seconds and --timeout-seconds must be positive")
    source, output_root = args.source_case.resolve(), args.output_root.resolve()
    if not source.is_file():
        print(f"Error: source case not found: {source}", file=sys.stderr)
        return 2
    actual_hash = file_hash(source)
    if actual_hash != args.source_sha256.lower():
        print("Error: source case hash does not match the approved QA source.", file=sys.stderr)
        return 2
    target = run_directory(output_root)
    launch = [
        sys.executable, str(ROOT / "scripts" / "launch_readonly_case.py"),
        "--fluent-root", str(args.fluent_root.resolve()), "--source-case", str(source),
        "--output-dir", str(target),
    ]
    if args.dry_run:
        print(json.dumps({"title_contains": args.title_contains, "source_sha256": actual_hash, "output_dir": str(target), "command": launch}, ensure_ascii=False, indent=2))
        return 0
    deadline = time.monotonic() + args.timeout_seconds
    while time.monotonic() < deadline:
        if not find_windows(args.title_contains):
            target.mkdir(parents=True, exist_ok=False)
            metadata = target / "queued-rerun.json"
            metadata.write_text(json.dumps({
                "waited_for_title": args.title_contains,
                "source_case": str(source), "source_sha256": actual_hash,
                "command": launch,
                "queued_at": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            with (target / "rerun-launch.log").open("w", encoding="utf-8") as log:
                process = subprocess.Popen(launch, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            print(f"Started isolated visual-QA rerun, PID {process.pid}: {target}")
            return 0
        time.sleep(args.poll_seconds)
    print("Timed out waiting for the Fluent Home window to close.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
