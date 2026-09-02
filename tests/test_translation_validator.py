from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_translation import check_catalog, check_json, check_xml


class TranslationValidatorTests(unittest.TestCase):
    def test_json_preserves_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ok.json"
            path.write_text('{"Value: %1": "Значение: %1"}', encoding="utf-8")
            self.assertEqual(check_json(path), [])

    def test_json_detects_lost_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"Value: %1": "Значение"}', encoding="utf-8")
            self.assertTrue(check_json(path))

    def test_xml_detects_invalid_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.ts"
            path.write_text("<TS><context></TS>", encoding="utf-8")
            self.assertTrue(check_xml(path))

    def test_catalog_rejects_review_without_reviewer(self) -> None:
        data = {
            "format_version": 1,
            "fluent_version": "2026 R1",
            "source_locale": "en",
            "target_locale": "ru",
            "entries": [{
                "id": "solver:residuals",
                "module": "solver",
                "qt_context": "QObject",
                "source": "Residuals",
                "translation": "Невязки",
                "status": "reviewed",
                "context": "Solver",
                "comment": "",
            }],
        }
        errors, _ = check_catalog(Path("catalog.json"), data)
        self.assertTrue(any("review.reviewer" in error for error in errors))

    def test_catalog_rejects_duplicate_id(self) -> None:
        entry = {
            "id": "same:id",
            "module": "same",
            "qt_context": "QObject",
            "source": "Residuals",
            "translation": "Невязки",
            "status": "translated",
            "context": "Solver",
            "comment": "",
        }
        data = {
            "format_version": 1,
            "fluent_version": "2026 R1",
            "source_locale": "en",
            "target_locale": "ru",
            "entries": [entry, entry],
        }
        errors, _ = check_catalog(Path("catalog.json"), data)
        self.assertTrue(any("повторяющийся id" in error for error in errors))

    def test_catalog_enforces_glossary(self) -> None:
        data = {
            "format_version": 1,
            "fluent_version": "2026 R1",
            "source_locale": "en",
            "target_locale": "ru",
            "entries": [{
                "id": "solver:residuals",
                "module": "solver",
                "qt_context": "QObject",
                "source": "Residuals",
                "translation": "Остатки",
                "status": "translated",
                "context": "Solver",
                "comment": "",
            }],
        }
        errors, _ = check_catalog(Path("catalog.json"), data, {"Residuals": "Невязки"})
        self.assertTrue(any("расходится с глоссарием" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
