#!/usr/bin/env python3
"""Scenario-based, read-only visual QA planning for Fluent localization.

The runner intentionally separates *navigation* from *classification*: it may
invoke only the existing whitelisted UIA/coordinate helpers, and never writes
Fluent data.  A human or Computer Use agent reviews the captured real frame
and records evidence in reviews/v2026R1/windows.yml afterwards.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.check_visual_review import changed_modules, read_json, validate_review
    from scripts.report_progress import load_catalog, load_inventory, metrics
except ModuleNotFoundError:  # pragma: no cover - direct script execution.
    from check_visual_review import changed_modules, read_json, validate_review
    from report_progress import load_catalog, load_inventory, metrics


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = ROOT / "qa_scenarios"
REVIEWS = ROOT / "reviews" / "v2026R1" / "windows.yml"
CATALOG = ROOT / "translations" / "v2026R1" / "catalog.json"
INVENTORY = ROOT / "profiles" / "v2026R1_inventory.json"
AVAILABILITY = {
    "always_accessible", "requires_case", "requires_model", "requires_solver_mode",
    "requires_boundary_type", "requires_results", "requires_operation", "semi_automatic", "manual_only",
}
AUTOMATION = {"automatic", "semi_automatic", "manual_only"}


def load_scenarios(directory: Path = SCENARIO_DIR) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.yml")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid scenario JSON/YAML subset: {path}: {error}") from error
        if not isinstance(value, dict):
            raise ValueError(f"Scenario must be an object: {path}")
        value["_path"] = path
        scenarios.append(value)
    return scenarios


def validate_scenarios(scenarios: Iterable[dict[str, Any]], windows: Iterable[dict[str, Any]], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    known_windows = {str(window.get("id")) for window in windows}
    ids: set[str] = set()
    step_ids: set[str] = set()
    for scenario in scenarios:
        where = str(scenario.get("_path", scenario.get("id", "scenario")))
        identifier = scenario.get("id")
        if scenario.get("format_version") != 1:
            errors.append(f"{where}: format_version must be 1")
        if not isinstance(identifier, str) or not identifier:
            errors.append(f"{where}: id is required")
        elif identifier in ids:
            errors.append(f"{where}: duplicate scenario id {identifier}")
        else:
            ids.add(identifier)
        if scenario.get("tier") not in {1, 2, 3}:
            errors.append(f"{where}: tier must be 1, 2, or 3")
        if scenario.get("automation") not in AUTOMATION:
            errors.append(f"{where}: unsupported automation mode")
        local_case = scenario.get("local_qa_case")
        if local_case is not None:
            if not isinstance(local_case, str) or not local_case:
                errors.append(f"{where}: local_qa_case must be a non-empty relative path")
            else:
                candidate = (root / local_case).resolve()
                if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
                    errors.append(f"{where}: local QA case is missing: {local_case}")
        if not isinstance(scenario.get("limitations"), list):
            errors.append(f"{where}: limitations must be an array")
        steps = scenario.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append(f"{where}: steps must be a non-empty array")
            continue
        for step in steps:
            if not isinstance(step, dict):
                errors.append(f"{where}: every step must be an object")
                continue
            step_id = step.get("id")
            if not isinstance(step_id, str) or not step_id:
                errors.append(f"{where}: step without id")
                continue
            if step_id in step_ids:
                errors.append(f"{where}: duplicate window step {step_id}")
            step_ids.add(step_id)
            if step_id not in known_windows:
                errors.append(f"{where}: step {step_id} has no review metadata")
            if not isinstance(step.get("target"), str) or not step["target"]:
                errors.append(f"{where}: {step_id} needs a target")
            modules = step.get("modules")
            if not isinstance(modules, list) or not modules or not all(isinstance(module, str) and module for module in modules):
                errors.append(f"{where}: {step_id} needs one or more modules")
            if not isinstance(step.get("capture"), str) or not step["capture"].endswith((".png", ".jpg", ".jpeg")):
                errors.append(f"{where}: {step_id} needs an image capture filename")
            if step.get("availability") not in AVAILABILITY:
                errors.append(f"{where}: {step_id} has unsupported availability")
    return errors


def scenario_steps(scenarios: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(step, scenario=scenario["id"], tier=scenario["tier"]) for scenario in scenarios for step in scenario["steps"]]


def coverage(scenarios: Iterable[dict[str, Any]], windows: Iterable[dict[str, Any]], package: str | None = None) -> dict[int, Counter[str]]:
    by_id = {str(window["id"]): window for window in windows}
    result: dict[int, Counter[str]] = defaultdict(Counter)
    for step in scenario_steps(scenarios):
        window = by_id[step["id"]]
        state = str(window.get("status", "unverified"))
        if package is not None and window.get("package") != package:
            state = "needs_recheck" if state != "unverified" else "unverified"
        result[int(step["tier"])][state] += 1
        if step["availability"] == "manual_only":
            result[int(step["tier"])]["manual_only"] += 1
        if window.get("beta_blocker") is True and (package is None or window.get("package") == package):
            result[int(step["tier"])]["beta_blocker"] += 1
    return result


def render_coverage(data: dict[int, Counter[str]], package: str | None = None, translation: dict[str, int] | None = None) -> str:
    heading = "## Visual QA coverage" + (f" for `{package}`" if package else "")
    lines = [heading, ""]
    if translation is not None:
        percent = translation["translated"] / translation["total"] * 100 if translation["total"] else 0
        lines.extend([f"Translation coverage: {translation['translated']:,} / {translation['total']:,} ({percent:.1f}%)", ""])
    lines.extend(["| Tier | Verified | Partial | Captured | Review required | Needs recheck | Unverified | Manual-only | Beta blockers |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for tier in (1, 2, 3):
        row = data.get(tier, Counter())
        lines.append("| {tier} | {verified} | {partial} | {captured} | {review_required} | {needs_recheck} | {unverified} | {manual_only} | {beta_blocker} |".format(tier=tier, **{name: row[name] for name in ("verified", "partial", "captured", "review_required", "needs_recheck", "unverified", "manual_only", "beta_blocker")}))
    return "\n".join(lines) + "\n"


def affected_steps(scenarios: Iterable[dict[str, Any]], modules: set[str]) -> list[dict[str, Any]]:
    return [step for step in scenario_steps(scenarios) if modules.intersection(step["modules"])]


def mark_needs_recheck(reviews_path: Path, steps: Iterable[dict[str, Any]]) -> list[str]:
    data = read_json(reviews_path)
    ids = {step["id"] for step in steps}
    changed: list[str] = []
    for window in data["windows"]:
        if window.get("id") in ids and window.get("status") == "verified":
            window["status"] = "needs_recheck"
            window["issues"] = ["A linked translation module changed; capture and review this window again."]
            window.pop("beta_blocker", None)
            changed.append(str(window["id"]))
    if changed:
        reviews_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def attach_capture(reviews_path: Path, window_id: str, image_path: Path, package: str, scope: str, root: Path = ROOT) -> None:
    """Attach a real local image and mark the corresponding window captured."""
    root = root.resolve()
    image_path = image_path.resolve()
    allowed = root / "build"
    if not image_path.is_relative_to(allowed) or not image_path.parent.name.startswith("visual-qa-"):
        raise ValueError("Evidence image must be inside build/visual-qa-*")
    image = image_path.read_bytes()
    if not (image.startswith(b"\xff\xd8\xff") or image.startswith(b"\x89PNG\r\n\x1a\n")):
        raise ValueError("Evidence image must be a JPEG or PNG")
    data = read_json(reviews_path)
    for window in data["windows"]:
        if window.get("id") == window_id:
            window.update({
                "status": "captured", "last_checked": date.today().isoformat(),
                "package": package, "scope": scope,
                "evidence": {"path": image_path.relative_to(root).as_posix(), "sha256": hashlib.sha256(image).hexdigest()},
                "issues": ["Frame captured automatically; visual classification is still required."],
            })
            window.pop("beta_blocker", None)
            reviews_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return
    raise ValueError(f"Unknown review window: {window_id}")


def run_navigation(steps: list[dict[str, Any]], settle_seconds: float) -> int:
    for step in steps:
        route = step.get("route")
        if not route:
            print(f"Manual/Computer Use navigation required: {step['id']} ({step['target']})")
            continue
        if str(route).startswith("uia:"):
            command = [sys.executable, str(ROOT / "scripts" / "navigate_fluent_uia.py"), "--target", str(route).split(":", 1)[1], "--settle-seconds", str(settle_seconds)]
        else:
            command = [sys.executable, str(ROOT / "scripts" / "navigate_fluent_visual_qa.py"), "--mode", str(route), "--settle-seconds", str(settle_seconds)]
        print("Safe navigation:", " ".join(command))
        completed = subprocess.run(command, cwd=ROOT)
        if completed.returncode:
            return completed.returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scenario-based Fluent visual QA")
    parser.add_argument("--scenarios", type=Path, default=SCENARIO_DIR)
    parser.add_argument("--reviews", type=Path, default=REVIEWS)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List scenarios and safe navigation constraints")
    sub.add_parser("validate", help="Validate scenario and review cross-references")
    coverage_parser = sub.add_parser("coverage", help="Report visual QA coverage by tier")
    coverage_parser.add_argument("--package")
    affected_parser = sub.add_parser("affected", help="Find scenarios affected by translation changes")
    affected_parser.add_argument("--base-ref", required=True)
    affected_parser.add_argument("--apply", action="store_true", help="Change verified affected windows to needs_recheck")
    capture_parser = sub.add_parser("record-capture", help="Attach an automatically captured real image as captured")
    capture_parser.add_argument("--window", required=True)
    capture_parser.add_argument("--image", type=Path, required=True)
    capture_parser.add_argument("--package", required=True)
    capture_parser.add_argument("--scope", required=True)
    run_parser = sub.add_parser("run", help="Print or execute only whitelisted navigation routes")
    run_parser.add_argument("scenario", nargs="?", help="Scenario id")
    run_parser.add_argument("--tier", type=int, choices=(1, 2, 3))
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--execute-navigation", action="store_true", help="Invoke existing safe UIA/coordinate navigation; Fluent must already be open")
    run_parser.add_argument("--settle-seconds", type=float, default=8)
    args = parser.parse_args()
    try:
        windows, review_errors = validate_review(read_json(args.reviews))
        scenarios = load_scenarios(args.scenarios)
        errors = review_errors + validate_scenarios(scenarios, windows)
        if errors:
            raise ValueError("\n".join(errors))
        if args.command == "validate":
            print(f"Validated {len(scenarios)} scenarios and {len(windows)} review records.")
            return 0
        if args.command == "list":
            for scenario in scenarios:
                print(f"{scenario['id']}: Tier {scenario['tier']}; {scenario['automation']}; {len(scenario['steps'])} windows")
            return 0
        if args.command == "coverage":
            print(render_coverage(coverage(scenarios, windows, args.package), args.package, metrics(load_catalog(args.catalog), load_inventory(args.inventory))), end="")
            return 0
        if args.command == "affected":
            modules = changed_modules(args.base_ref, args.catalog)
            steps = affected_steps(scenarios, modules)
            print("Changed modules:", ", ".join(sorted(modules)) or "none")
            for step in steps:
                print(f"- {step['id']} ({step['scenario']}): {', '.join(sorted(modules.intersection(step['modules'])))}")
            if args.apply:
                print("Marked needs_recheck:", ", ".join(mark_needs_recheck(args.reviews, steps)) or "none")
            return 0
        if args.command == "record-capture":
            attach_capture(args.reviews, args.window, args.image, args.package, args.scope)
            print(f"Recorded captured evidence for {args.window}; review is still required.")
            return 0
        selected = [scenario for scenario in scenarios if (args.scenario is None or scenario["id"] == args.scenario) and (args.tier is None or scenario["tier"] == args.tier)]
        if not selected:
            raise ValueError("No matching scenario")
        steps = [step for scenario in selected for step in scenario_steps([scenario])]
        for step in steps:
            print(f"{step['scenario']}: {step['id']} -> {step['target']} [{step['availability']}] capture={step['capture']}")
        if args.execute_navigation:
            return run_navigation(steps, args.settle_seconds)
        if not args.dry_run:
            print("Plan only. Add --execute-navigation only after Fluent is open on an isolated QA case.")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
