#!/usr/bin/env python3
"""Confirm that an isolated Fluent QA case, not just Home, became ready.

This read-only verifier never sends input to Fluent.  It distinguishes a
visible empty Home window from a loaded copy of the approved case and turns
known startup failures (especially licensing) into structured evidence.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.capture_fluent_window import find_windows
except ModuleNotFoundError:  # pragma: no cover - direct execution path.
    from capture_fluent_window import find_windows


def classify(titles: list[str], case_title_fragment: str, error_text: str) -> tuple[str, str]:
    """Classify a startup observation without relying on a screenshot alone."""
    needle = case_title_fragment.casefold()
    if any(needle in title.casefold() and "fluent@home" in title.casefold() for title in titles):
        return "ready", "Loaded QA case is visible in the Fluent@Home title."
    lowered = error_text.casefold()
    if "unexpected license problem" in lowered:
        return "license_error", "Fluent reported an unexpected license problem."
    if "abnormal exit" in lowered:
        return "abnormal_exit", "Fluent reported an abnormal exit."
    return "waiting", "Waiting for the loaded QA case title or a startup error."


def current_startup_text(runtime_dir: Path, since: float) -> str:
    """Read only current error logs and transcripts, never stale failures."""
    chunks: list[str] = []
    for pattern in ("fluent-*-error.log", "fluent-*.trn"):
        for path in runtime_dir.glob(pattern):
            if path.stat().st_mtime >= since:
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def write_status(path: Path, status: str, detail: str, titles: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "status": status,
        "detail": detail,
        "visible_titles": titles,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for an isolated Fluent QA case to finish loading")
    parser.add_argument("--case-title-fragment", required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--status-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--ready-stable-seconds", type=float, default=10.0)
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.poll_seconds <= 0 or args.ready_stable_seconds <= 0:
        parser.error("timeout, poll, and ready-stable seconds must be positive")
    runtime = args.runtime_dir.resolve()
    started = time.time()
    deadline = time.monotonic() + args.timeout_seconds
    ready_since: float | None = None
    while time.monotonic() < deadline:
        titles = [title for _, title in find_windows("Fluent@Home")]
        status, detail = classify(titles, args.case_title_fragment, current_startup_text(runtime, started))
        if status in {"license_error", "abnormal_exit"}:
            write_status(args.status_file, status, detail, titles)
            print(f"Fluent QA startup status: {status}: {detail}")
            return 2
        if status == "ready":
            ready_since = ready_since or time.monotonic()
            if time.monotonic() - ready_since >= args.ready_stable_seconds:
                write_status(args.status_file, status, detail, titles)
                print(f"Fluent QA startup status: {status}: {detail}")
                return 0
        else:
            ready_since = None
        time.sleep(args.poll_seconds)
    titles = [title for _, title in find_windows("Fluent@Home")]
    write_status(args.status_file, "timeout", "Timed out waiting for the loaded QA case.", titles)
    print("Fluent QA startup status: timeout", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
