from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_repository import inspect_file


class RepositoryCheckTests(unittest.TestCase):
    def test_rejects_forbidden_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "vendor.dll"
            path.write_bytes(b"not actually a DLL")
            self.assertTrue(inspect_file(root, path))

    def test_rejects_renamed_windows_binary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "resource.txt"
            path.write_bytes(b"MZ" + b"\0" * 32)
            self.assertTrue(inspect_file(root, path))

    def test_accepts_normal_translation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "translation.json"
            path.write_text('{"Residuals": "Невязки"}', encoding="utf-8")
            self.assertEqual(inspect_file(root, path), [])

    def test_rejects_extracted_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "block.extracted.json"
            path.write_text('{"strings": []}', encoding="utf-8")
            self.assertTrue(inspect_file(root, path))


if __name__ == "__main__":
    unittest.main()
