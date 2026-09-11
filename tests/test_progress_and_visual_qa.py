from __future__ import annotations

import unittest
from pathlib import Path

from scripts.check_visual_review import render_summary, validate_review
from scripts.report_progress import metrics, module_rows, render_markdown
from scripts.apply_translation_batch import object_bounds
from scripts.check_beta_readiness import readiness_issues
from scripts.capture_fluent_window import encode_png_bgra, safe_name
from scripts.launch_fluent import fluent_command
from scripts.check_visual_journal import unsafe_lines
from scripts.navigate_fluent_visual_qa import HOME_STEPS, RECT, select_home_window


class ProgressReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = {
            "entries": [
                {"id": "One:a", "module": "One", "status": "translated"},
                {"id": "One:b", "module": "One", "status": "needs_context"},
                {"id": "Two:a", "module": "Two", "status": "reviewed"},
                {"id": "Two:b", "module": "Two", "status": "do_not_translate"},
            ]
        }
        self.inventory = {"total_messages": 10, "module_messages": {"One": 4, "Two": 3}}

    def test_metrics_count_reviewed_as_translated(self) -> None:
        result = metrics(self.catalog, self.inventory)
        self.assertEqual(result["translated"], 2)
        self.assertEqual(result["catalogued"], 4)
        self.assertEqual(result["not_catalogued"], 6)

    def test_module_rows_and_delta_markdown(self) -> None:
        rows = module_rows(self.catalog, self.inventory)
        first = next(row for row in rows if row["module"] == "One")
        self.assertEqual(first["translated"], 1)
        report = render_markdown(metrics(self.catalog, self.inventory), rows, ["Two"], False, {"total": 10, "translated": 1, "needs_review": 0, "needs_context": 2})
        self.assertIn("| Two | 1 | 2 | 3 | 33.3% |", report)
        self.assertIn("Change in this revision", report)


class VisualQaTests(unittest.TestCase):
    def test_valid_review_and_summary(self) -> None:
        windows, errors = validate_review(
            {
                "format_version": 1,
                "windows": [
                    {
                        "id": "general",
                        "window": "General",
                        "modules": ["TaskPage_General"],
                        "status": "verified",
                        "last_checked": "2026-09-07",
                        "package": "release-5009",
                        "scope": "mesh_only",
                        "issues": [],
                    }
                ],
            }
        )
        self.assertEqual(errors, [])
        self.assertIn("| Verified | 1 |", render_summary(windows, []))

    def test_verified_window_with_issues_is_rejected(self) -> None:
        _, errors = validate_review(
            {
                "format_version": 1,
                "windows": [
                    {
                        "id": "bad",
                        "window": "Bad",
                        "modules": ["Module"],
                        "status": "verified",
                        "last_checked": "2026-09-07",
                        "package": "release-5009",
                        "scope": "mesh_only",
                        "issues": ["English text remains."],
                    }
                ],
            }
        )
        self.assertTrue(errors)


class TranslationBatchTests(unittest.TestCase):
    def test_object_bounds_accepts_compact_and_indented_entries(self) -> None:
        compact = '{"entries":[{"id":"One:a","source":"A"}]}'
        start, end = object_bounds(compact, "One:a")
        self.assertEqual(compact[start:end], '{"id":"One:a","source":"A"}')

        indented = '{\n  "entries": [\n    {\n      "id": "One:b",\n      "source": "B"\n    }\n  ]\n}'
        start, end = object_bounds(indented, "One:b")
        self.assertIn('"source": "B"', indented[start:end])


class BetaReadinessTests(unittest.TestCase):
    def test_requires_current_package_and_visual_status(self) -> None:
        current = {"not_catalogued": 0, "needs_context": 0, "needs_review": 0}
        windows = [{"id": "one", "package": "old", "status": "verified"}]
        issues = readiness_issues(current, windows, "new", ("one", "missing"))
        self.assertIn("one was not checked against new (recorded package: old).", issues)
        self.assertIn("Required visual-QA window is missing: missing.", issues)

    def test_accepts_reviewed_current_window(self) -> None:
        current = {"not_catalogued": 0, "needs_context": 0, "needs_review": 0}
        windows = [{"id": "one", "package": "current", "status": "partial"}]
        self.assertEqual(readiness_issues(current, windows, "current", ("one",)), [])


class VisualCaptureTests(unittest.TestCase):
    def test_png_encoder_and_safe_name(self) -> None:
        png = encode_png_bgra(1, 1, bytes((10, 20, 30, 255)))
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(safe_name("Fluent@Home [3d]"), "Fluent-Home-3d")

    def test_launch_command_appends_journal_after_fluent_arguments(self) -> None:
        command = fluent_command(Path("fluent.exe"), ["3d", "-t1"], Path("safe-qa.jou"))
        self.assertEqual(command, ["fluent.exe", "3d", "-t1", "-i", "safe-qa.jou"])

    def test_visual_journal_permits_navigation_and_rejects_mutation(self) -> None:
        safe = '(cx-gui-do cx-set-list-tree-selections "NavigationPane*List_Tree1" (list "Setup|General"))\n(sleep 5)'
        self.assertEqual(unsafe_lines(safe), [])
        self.assertEqual(unsafe_lines('/solve/initialize/initialize-flow'), [(1, '/solve/initialize/initialize-flow')])

    def test_coordinate_navigation_is_limited_to_visible_home_tree(self) -> None:
        self.assertEqual([step[0] for step in HOME_STEPS], ["materials", "graphics", "surfaces"])
        for _, x, y in HOME_STEPS:
            self.assertLess(x, 0.2)
            self.assertGreater(y, 0.3)
            self.assertLess(y, 0.5)

    def test_coordinate_navigation_ignores_splash_window(self) -> None:
        splash = RECT(0, 0, 2000, 1000)
        home = RECT(0, 0, 1400, 900)
        self.assertEqual(select_home_window([(1, "Fluent", splash), (2, "Parallel Fluent@Home", home)])[0], 2)
        self.assertIsNone(select_home_window([(1, "Fluent", splash)]))


if __name__ == "__main__":
    unittest.main()
