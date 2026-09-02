from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_translation import check_json, check_xml


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


if __name__ == "__main__":
    unittest.main()
