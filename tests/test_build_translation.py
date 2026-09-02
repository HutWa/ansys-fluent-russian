from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as etree
from pathlib import Path

from scripts.build_translation import render_ts


class BuildTranslationTests(unittest.TestCase):
    def test_render_ts_skips_unresolved_entries(self) -> None:
        entries = [
            {
                "qt_context": "QObject",
                "source": "Residuals",
                "translation": "Невязки",
                "status": "translated",
                "comment": "",
            },
            {
                "qt_context": "QObject",
                "source": "Cell",
                "translation": "",
                "status": "needs_context",
                "comment": "Нужна панель.",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "module.ts"
            count = render_ts(entries, output)
            root = etree.parse(output).getroot()
        self.assertEqual(count, 1)
        self.assertEqual(root.findtext("context/message/source"), "Residuals")
        self.assertEqual(root.findtext("context/message/translation"), "Невязки")


if __name__ == "__main__":
    unittest.main()
