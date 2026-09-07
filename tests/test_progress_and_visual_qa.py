from __future__ import annotations

import unittest

from scripts.check_visual_review import render_summary, validate_review
from scripts.report_progress import metrics, module_rows, render_markdown


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


if __name__ == "__main__":
    unittest.main()
