from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scripts.check_beta_readiness import tier1_windows
from scripts.qa import affected_steps, attach_capture, coverage, load_scenarios, mark_needs_recheck, scenario_steps, validate_scenarios


class QaScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.windows = [
            {"id": "one", "status": "verified", "package": "current", "modules": ["One"], "issues": []},
            {"id": "two", "status": "partial", "package": "current", "modules": ["Two"], "issues": ["English"]},
        ]
        self.scenarios = [{
            "format_version": 1, "id": "basic", "name": "Basic", "tier": 1,
            "case_requirement": "requires_case", "automation": "semi_automatic", "limitations": [],
            "steps": [
                {"id": "one", "target": "One", "modules": ["One"], "capture": "one.png", "availability": "always_accessible"},
                {"id": "two", "target": "Two", "modules": ["Two"], "capture": "two.jpg", "availability": "manual_only"},
            ],
        }]

    def test_repository_scenarios_validate(self) -> None:
        scenarios = load_scenarios()
        review_data = json.loads((Path(__file__).parents[1] / "reviews/v2026R1/windows.yml").read_text(encoding="utf-8"))
        self.assertEqual(validate_scenarios(scenarios, review_data["windows"]), [])
        self.assertIn("cell-zone-conditions", tier1_windows())
        self.assertNotIn("energy-model", tier1_windows())

    def test_invalid_scenario_and_missing_case_are_rejected(self) -> None:
        invalid = dict(self.scenarios[0], tier=4, local_qa_case="qa_cases/missing.cas.h5")
        errors = validate_scenarios([invalid], self.windows, Path.cwd())
        self.assertTrue(any("tier" in error for error in errors))
        self.assertTrue(any("local QA case is missing" in error for error in errors))

    def test_coverage_and_module_mapping(self) -> None:
        result = coverage(self.scenarios, self.windows, "current")
        self.assertEqual(result[1]["verified"], 1)
        self.assertEqual(result[1]["partial"], 1)
        self.assertEqual(result[1]["manual_only"], 1)
        self.assertEqual([step["id"] for step in affected_steps(self.scenarios, {"Two"})], ["two"])
        self.assertEqual(len(scenario_steps(self.scenarios)), 2)

    def test_changed_verified_window_becomes_needs_recheck(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reviews = Path(directory) / "windows.yml"
            reviews.write_text(json.dumps({"format_version": 1, "windows": self.windows}), encoding="utf-8")
            changed = mark_needs_recheck(reviews, affected_steps(self.scenarios, {"One"}))
            self.assertEqual(changed, ["one"])
            saved = json.loads(reviews.read_text(encoding="utf-8"))
            self.assertEqual(saved["windows"][0]["status"], "needs_recheck")

    def test_capture_is_recorded_but_not_marked_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "build" / "visual-qa-test" / "one.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"\x89PNG\r\n\x1a\nframe")
            reviews = root / "windows.yml"
            reviews.write_text(json.dumps({"format_version": 1, "windows": self.windows}), encoding="utf-8")
            attach_capture(reviews, "one", image, "current", "isolated", root)
            saved = json.loads(reviews.read_text(encoding="utf-8"))
            self.assertEqual(saved["windows"][0]["status"], "captured")
            self.assertIn("sha256", saved["windows"][0]["evidence"])
