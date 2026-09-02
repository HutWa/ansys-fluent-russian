import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.launch_fluent import find_launcher, localized_environment


class LaunchFluentTests(unittest.TestCase):
    def test_find_windows_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            launcher = root / "ntbin" / "win64" / "fluent.exe"
            launcher.parent.mkdir(parents=True)
            launcher.touch()
            self.assertEqual(find_launcher(root), launcher)

    def test_localized_environment_is_child_only(self) -> None:
        with patch.dict(os.environ, {"lang": "en-us"}):
            environment = localized_environment()
            self.assertEqual(environment["lang"], "ru")
            self.assertEqual(os.environ["lang"], "en-us")


if __name__ == "__main__":
    unittest.main()
