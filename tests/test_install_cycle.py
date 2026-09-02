from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class InstallCycleTests(unittest.TestCase):
    def test_created_catalog_is_removed_on_uninstall(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fluent_root = root / "v261" / "fluent"
            language_root = fluent_root / "fluent26.1.0" / "cortex" / "resources" / "language"
            language_root.mkdir(parents=True)
            staging = root / "staging"
            staging.mkdir()
            catalog = staging / "DisplayProperties.qm"
            catalog.write_bytes(b"project-authored-qm")
            digest = hashlib.sha256(catalog.read_bytes()).hexdigest()
            (staging / "build-manifest.json").write_text(
                json.dumps({
                    "format_version": 1,
                    "fluent_version": "2026 R1",
                    "locale": "ru",
                    "modules": [{
                        "module": "DisplayProperties",
                        "file": catalog.name,
                        "messages": 1,
                        "sha256": digest,
                    }],
                }),
                encoding="utf-8",
            )
            backup = root / "backup"
            subprocess.run(
                [
                    sys.executable, str(repository / "scripts" / "install.py"),
                    "--fluent-root", str(fluent_root), "--staging-dir", str(staging),
                    "--backup-dir", str(backup), "--apply",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            installed = language_root / "ru" / catalog.name
            self.assertTrue(installed.is_file())
            subprocess.run(
                [
                    sys.executable, str(repository / "scripts" / "uninstall.py"),
                    "--backup-dir", str(backup), "--apply",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertFalse(installed.exists())
            self.assertFalse(installed.parent.exists())


if __name__ == "__main__":
    unittest.main()
