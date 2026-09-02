from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.extract_strings import message_id, parse_ts


class ExtractStringsTests(unittest.TestCase):
    def test_message_id_is_stable_and_context_sensitive(self) -> None:
        first = message_id("Module", "Panel", "Cell", "")
        self.assertEqual(first, message_id("Module", "Panel", "Cell", ""))
        self.assertNotEqual(first, message_id("Module", "Mesh", "Cell", ""))

    def test_parse_ts_preserves_context_and_reference(self) -> None:
        document = """<?xml version="1.0" encoding="utf-8"?>
<TS version="2.1" language="ja">
  <context><name>QObject</name><message>
    <source>Value: %1</source><translation>値: %1</translation>
  </message></context>
</TS>"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Module.ts"
            path.write_text(document, encoding="utf-8")
            entries = parse_ts(path, "Module")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["context"], "QObject")
        self.assertEqual(entries[0]["source"], "Value: %1")
        self.assertEqual(entries[0]["reference_translation"], "値: %1")


if __name__ == "__main__":
    unittest.main()
