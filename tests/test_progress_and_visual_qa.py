from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts.check_visual_review import render_summary, validate_review, verify_local_evidence
from scripts.report_progress import metrics, module_rows, render_markdown
from scripts.apply_translation_batch import object_bounds
from scripts.check_beta_readiness import readiness_issues
from scripts.capture_fluent_window import encode_png_bgra, safe_name
from scripts.launch_fluent import fluent_command
from scripts.check_visual_journal import unsafe_lines
from scripts.navigate_fluent_visual_qa import FILE_RIBBON_STEPS, HOME_STEPS, MATERIALS_TREE_STEPS, MODELS_EXPAND_STEPS, MULTIPHASE_DIALOG_STEPS, MULTIPHASE_TREE_STEPS, PHYSICS_RIBBON_STEPS, RECT, SOLUTION_CONTROLS_STEPS, SOLUTION_INITIALIZATION_STEPS, SOLUTION_METHODS_STEPS, VK_DOWN, VK_RETURN, VK_RIGHT, route_steps, select_home_window
from scripts.launch_readonly_case import read_only_journal
from scripts.wait_for_readonly_case_ready import classify
from scripts.wait_for_fluent_exit import fluent_processes_present, run_directory
from scripts.inspect_fluent_uia import inspect_target
from scripts.navigate_fluent_uia import SAFE_TARGETS, SINGLE_CLICK_TARGETS


ROOT = Path(__file__).resolve().parents[1]


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
    def test_local_evidence_is_optional(self) -> None:
        self.assertEqual(verify_local_evidence([{"id": "old"}]), [])

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
                        "evidence": {"path": "build/visual-qa-test/general.png", "sha256": "0" * 64},
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

    def test_verified_window_without_evidence_is_rejected(self) -> None:
        _, errors = validate_review({"format_version": 1, "windows": [{
            "id": "bad", "window": "Bad", "modules": ["Module"], "status": "verified",
            "last_checked": "2026-09-22", "package": "current", "scope": "dialog", "issues": [],
        }]})
        self.assertTrue(any("no captured evidence" in error for error in errors))

    def test_beta_blocker_requires_partial_issue(self) -> None:
        _, errors = validate_review({"format_version": 1, "windows": [{
            "id": "bad", "window": "Bad", "modules": ["Module"], "status": "verified",
            "last_checked": "2026-09-22", "package": "current", "scope": "dialog",
            "beta_blocker": True, "issues": [],
        }]})
        self.assertTrue(any("beta_blocker requires partial status" in error for error in errors))


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
        windows = [{"id": "one", "package": "current", "status": "partial", "evidence": {"path": "build/visual-qa-test/one.png", "sha256": "0" * 64}}]
        self.assertEqual(readiness_issues(current, windows, "current", ("one",)), [])

    def test_rejects_critical_defect_even_when_window_was_reviewed(self) -> None:
        current = {"not_catalogued": 0, "needs_context": 0, "needs_review": 0}
        windows = [{"id": "one", "package": "current", "status": "partial", "evidence": {"path": "build/visual-qa-test/one.png", "sha256": "0" * 64}, "beta_blocker": True,
                    "issues": ["Internal path is visible."]}]
        self.assertEqual(readiness_issues(current, windows, "current", ("one",)),
                         ["one has a critical visual-QA defect recorded for current."])


class VisualCaptureTests(unittest.TestCase):
    def test_interactive_task_registration_never_uses_system_or_elevation(self) -> None:
        installer = (ROOT / "scripts" / "Register-FluentVisualQaTask.ps1").read_text(encoding="utf-8")
        self.assertIn("-LogonType Interactive", installer)
        self.assertIn("-RunLevel Limited", installer)
        self.assertNotIn("-UserId 'SYSTEM'", installer)
        self.assertIn("Codex Fluent QA Capture", installer)
        self.assertIn("Codex Fluent QA Models Tree", installer)
        self.assertIn("Codex Fluent QA Solution Methods", installer)
        self.assertIn("Codex Fluent QA Solution Controls", installer)
        self.assertIn("Codex Fluent QA Solution Initialization", installer)
        self.assertIn("Codex Fluent QA Run Calculation", installer)
        self.assertIn("Codex Fluent QA Materials", installer)
        self.assertIn("Codex Fluent QA Cell Zone Conditions", installer)
        self.assertIn("Codex Fluent QA Navigation Probe", installer)
        self.assertIn("Codex Fluent QA Read-Only Bioreactor", installer)
        capture = (ROOT / "scripts" / "capture_current_fluent_task.cmd").read_text(encoding="utf-8")
        self.assertIn('--title-contains "Fluent@Home"', capture)
        self.assertNotIn("navigate_", capture)
        models = (ROOT / "scripts" / "run_models_tree_visual_qa_task.cmd").read_text(encoding="utf-8")
        self.assertIn("--target models-tree", models)
        self.assertIn('--title-contains "Fluent@Home"', models)
        self.assertNotIn("--mode multiphase", models)
        methods = (ROOT / "scripts" / "run_solution_methods_visual_qa_task.cmd").read_text(encoding="utf-8")
        self.assertIn("--target solution-methods", methods)
        self.assertIn('--title-contains "Fluent@Home"', methods)
        controls = (ROOT / "scripts" / "run_solution_controls_visual_qa_task.cmd").read_text(encoding="utf-8")
        self.assertIn("--target solution-controls", controls)
        initialization = (ROOT / "scripts" / "run_solution_initialization_visual_qa_task.cmd").read_text(encoding="utf-8")
        self.assertIn("--target solution-initialization", initialization)
        calculation = (ROOT / "scripts" / "run_calculation_visual_qa_task.cmd").read_text(encoding="utf-8")
        self.assertIn("--target run-calculation", calculation)
        materials = (ROOT / "scripts" / "run_materials_visual_qa_task.cmd").read_text(encoding="utf-8")
        self.assertIn("--target materials", materials)
        cell_zone = (ROOT / "scripts" / "run_cell_zone_conditions_visual_qa_task.cmd").read_text(encoding="utf-8")
        self.assertIn("--target cell-zone-conditions", cell_zone)
        probe = (ROOT / "scripts" / "run_navigation_probe_visual_qa_task.cmd").read_text(encoding="utf-8")
        self.assertIn("inspect_fluent_uia.py", probe)
        self.assertNotIn("capture_fluent_window.py", probe)
        readonly_task = (ROOT / "scripts" / "run_readonly_bioreactor_task.cmd").read_text(encoding="utf-8")
        self.assertIn("--runtime-dir \"%QA_OUTPUT%\"", readonly_task)
        self.assertIn("wait_for_readonly_case_ready.py", readonly_task)

    def test_uia_navigation_has_only_whitelisted_task_pages(self) -> None:
        self.assertEqual(SAFE_TARGETS, {
            "run-calculation": "Запуск расчёта",
            "models-tree": "Модели",
            "solution-methods": "Методы",
            "solution-controls": "Управление",
            "solution-initialization": "Инициализация",
            "materials": "Материалы",
            "cell-zone-conditions": "Условия в ячеечных зонах",
        })
        self.assertEqual(SINGLE_CLICK_TARGETS, {
            "solution-initialization", "materials", "cell-zone-conditions",
        })
        uia_source = (ROOT / "scripts" / "navigate_fluent_uia.py").read_text(encoding="utf-8")
        self.assertIn("expander_x = item_rect.left - 12", uia_source)
        self.assertIn("Models tree expander is outside", uia_source)
        self.assertIn("Fluent did not render expected page heading", uia_source)
        self.assertIn("content_left = rect.left + round(rect.width() * 0.18)", uia_source)
        self.assertIn('action = "select-once"', uia_source)

    def test_uia_probe_only_collects_properties(self) -> None:
        with mock.patch("scripts.inspect_fluent_uia.fluent_window") as window:
            item = mock.Mock()
            parent = mock.Mock()
            item.window_text.return_value = "Материалы"
            item.parent.return_value = parent
            window.return_value.descendants.return_value = [item]
            for wrapper, name in ((item, "Материалы"), (parent, "Настройка")):
                wrapper.window_text.return_value = name
                wrapper.is_enabled.return_value = True
                wrapper.is_visible.return_value = True
                wrapper.children.return_value = []
                wrapper.element_info.control_type = "TreeItem"
                wrapper.element_info.automation_id = "id"
                wrapper.element_info.class_name = "class"
                wrapper.rectangle.return_value.left = 1
                wrapper.rectangle.return_value.top = 2
                wrapper.rectangle.return_value.right = 3
                wrapper.rectangle.return_value.bottom = 4
            snapshot = inspect_target("materials")
        self.assertEqual(snapshot["match_count"], 1)
        item.double_click_input.assert_not_called()
        item.type_keys.assert_not_called()

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
        self.assertEqual(VK_RETURN, 0x0D)
        self.assertEqual(VK_RIGHT, 0x27)
        self.assertEqual(VK_DOWN, 0x28)
        for _, x, y in HOME_STEPS:
            self.assertLess(x, 0.2)
            self.assertGreater(y, 0.3)
            self.assertLess(y, 0.5)
        self.assertEqual(PHYSICS_RIBBON_STEPS, (("physics-ribbon", 0.160, 0.047),))
        self.assertEqual(route_steps("multiphase-dialog"), MULTIPHASE_DIALOG_STEPS)
        self.assertEqual(route_steps("multiphase-tree"), MULTIPHASE_TREE_STEPS)
        self.assertEqual(route_steps("materials-tree"), MATERIALS_TREE_STEPS)
        self.assertEqual(route_steps("solution-methods"), SOLUTION_METHODS_STEPS)
        self.assertEqual(route_steps("solution-controls"), SOLUTION_CONTROLS_STEPS)
        self.assertEqual(route_steps("solution-initialization"), SOLUTION_INITIALIZATION_STEPS)
        self.assertEqual(route_steps("file-ribbon"), FILE_RIBBON_STEPS)
        self.assertEqual(route_steps("models-expand"), MODELS_EXPAND_STEPS)

    def test_coordinate_navigation_ignores_splash_window(self) -> None:
        splash = RECT(0, 0, 2000, 1000)
        home = RECT(0, 0, 1400, 900)
        self.assertEqual(select_home_window([(1, "Fluent", splash), (2, "Parallel Fluent@Home", home)])[0], 2)
        self.assertIsNone(select_home_window([(1, "Fluent", splash)]))

    def test_readonly_case_bootstrap_has_only_read_command(self) -> None:
        journal = read_only_journal(Path("build") / "case.cas.h5")
        self.assertEqual(journal.splitlines(), ["; Visual QA read-only bootstrap", '/file/read-case "build/case.cas.h5"'])
        self.assertNotIn("write", journal.casefold())
        self.assertNotIn("solve", journal.casefold())

    def test_readonly_launcher_records_fluent_output(self) -> None:
        launcher = (ROOT / "scripts" / "launch_readonly_case.py").read_text(encoding="utf-8")
        self.assertIn('fluent_log = output / "fluent-launch.log"', launcher)
        self.assertIn("stderr=subprocess.STDOUT", launcher)
        self.assertIn("Runtime directory for Fluent must contain ASCII characters only", launcher)
        self.assertIn('Path(tempfile.gettempdir()) / "ansys-fluent-russian-qa"', launcher)
        self.assertIn("command, cwd=runtime, env=localized_environment()", launcher)

    def test_readonly_startup_verifier_requires_loaded_case_and_detects_license(self) -> None:
        self.assertEqual(
            classify(["bioreactor_2026R1_test_setup Parallel Fluent@Home"], "bioreactor_2026R1_test_setup", ""),
            ("ready", "Loaded QA case is visible in the Fluent@Home title."),
        )
        self.assertEqual(
            classify(["Parallel Fluent@Home"], "bioreactor_2026R1_test_setup", "Unexpected license problem; exiting."),
            ("license_error", "Fluent reported an unexpected license problem."),
        )
        verifier = (ROOT / "scripts" / "wait_for_readonly_case_ready.py").read_text(encoding="utf-8")
        self.assertIn('("fluent-*-error.log", "fluent-*.trn")', verifier)

    def test_queued_rerun_directory_is_timestamped(self) -> None:
        instant = datetime(2026, 9, 25, 12, 34, 56, tzinfo=timezone.utc)
        self.assertEqual(
            run_directory(Path("build") / "visual-qa", instant),
            Path("build/visual-qa/rerun-20260925T123456Z"),
        )

    def test_queued_rerun_checks_for_existing_fluent_processes(self) -> None:
        with mock.patch("scripts.wait_for_fluent_exit.subprocess.run") as run:
            run.return_value.stdout = '"fluent.exe","1234","Console","1","42 K"\n'
            self.assertTrue(fluent_processes_present())
            run.return_value.stdout = "INFO: No tasks are running which match the specified criteria.\n"
            self.assertFalse(fluent_processes_present())


if __name__ == "__main__":
    unittest.main()
