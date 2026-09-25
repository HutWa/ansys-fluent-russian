#!/usr/bin/env python3
"""Report whether a Fluent localization package meets the beta-release gates."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.check_visual_review import validate_review
    from scripts.install import load_build
    from scripts.verify_installation import verify
    from scripts.qa import load_scenarios, scenario_steps
    from scripts.report_progress import load_catalog, load_inventory, metrics
except ModuleNotFoundError:
    from check_visual_review import validate_review
    from install import load_build
    from verify_installation import verify
    from qa import load_scenarios, scenario_steps
    from report_progress import load_catalog, load_inventory, metrics


ROOT = Path(__file__).resolve().parents[1]
def tier1_windows() -> tuple[str, ...]:
    """The beta gate follows scenario metadata, not a duplicate hard-coded list."""
    return tuple(step["id"] for step in scenario_steps(load_scenarios()) if step["tier"] == 1)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def readiness_issues(
    current: dict[str, int], windows: list[dict[str, Any]], package: str,
    required_windows: tuple[str, ...] | None = None,
) -> list[str]:
    issues: list[str] = []
    if current["not_catalogued"]:
        issues.append(f"{current['not_catalogued']:,} Fluent strings are not catalogued.")
    if current["needs_context"] or current["needs_review"]:
        issues.append(
            "Catalog still has "
            f"{current['needs_context']:,} needs-context and {current['needs_review']:,} needs-review entries."
        )
    by_id = {str(window.get("id")): window for window in windows}
    required_windows = required_windows if required_windows is not None else tier1_windows()
    for identifier in required_windows:
        window = by_id.get(identifier)
        if window is None:
            issues.append(f"Required visual-QA window is missing: {identifier}.")
            continue
        if window.get("package") != package:
            issues.append(
                f"{identifier} was not checked against {package} "
                f"(recorded package: {window.get('package', 'none')})."
            )
        elif window.get("status") in {"unverified", "needs_recheck", "manual_only", "captured", "review_required"}:
            issues.append(f"{identifier} still has visual-QA status {window['status']}.")
        elif window.get("beta_blocker") is True:
            issues.append(f"{identifier} has a critical visual-QA defect recorded for {package}.")
        elif "evidence" not in window:
            issues.append(f"{identifier} was checked against {package} without captured evidence.")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Fluent beta-release readiness")
    parser.add_argument("--catalog", type=Path, default=ROOT / "translations" / "v2026R1" / "catalog.json")
    parser.add_argument("--inventory", type=Path, default=ROOT / "profiles" / "v2026R1_inventory.json")
    parser.add_argument("--reviews", type=Path, default=ROOT / "reviews" / "v2026R1" / "windows.yml")
    parser.add_argument("--package", required=True, help="Package identifier being evaluated, for example release-27104-full")
    parser.add_argument("--staging-dir", type=Path, help="Optional built package to verify using build-manifest.json")
    parser.add_argument("--fluent-root", type=Path, help="Optional Fluent installation to verify against the build manifest")
    args = parser.parse_args()
    try:
        catalog = load_catalog(args.catalog)
        current = metrics(catalog, load_inventory(args.inventory))
        windows, review_errors = validate_review(read_json(args.reviews))
        if review_errors:
            raise ValueError("\n".join(review_errors))
        issues = readiness_issues(current, windows, args.package)
        built_modules: int | None = None
        if args.staging_dir:
            _, built = load_build(args.staging_dir)
            built_modules = len(built)
            expected_modules = len({
                str(entry["module"]) for entry in catalog["entries"]
                if entry.get("status") != "do_not_translate"
            })
            if built_modules != expected_modules:
                issues.append(
                    f"Build manifest is incomplete: {built_modules} of {expected_modules} catalog modules are present."
                )
            if args.fluent_root:
                mismatches = verify(args.fluent_root, args.staging_dir)
                if mismatches:
                    issues.append(f"Installed package does not match the build manifest: {len(mismatches)} module(s) differ.")
        elif args.fluent_root:
            raise ValueError("--fluent-root requires --staging-dir")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    print("## Fluent beta readiness\n")
    print(f"- Package: `{args.package}`")
    print(f"- Catalog: {current['translated']:,} translated / {current['total']:,}; {current['catalogued']:,} classified")
    if built_modules is not None:
        print(f"- Build manifest: {built_modules} Qt modules")
    if not issues:
        print("- Status: ready for the beta release gate")
        return 0
    print("- Status: not ready\n\n### Remaining gates\n")
    for issue in issues:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
