import os
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.config_paths import expand_path


class ConfigPathsTests(unittest.TestCase):
    def test_expands_windows_style_variables(self) -> None:
        with patch.dict(os.environ, {"FABRIC_AGENTIC_TEST_ROOT": "/opt/agentic"}, clear=False):
            path = expand_path("%FABRIC_AGENTIC_TEST_ROOT%/profile.json")

        self.assertNotIn("%", str(path))
        self.assertIn("agentic", str(path))

    def test_expands_posix_style_variables(self) -> None:
        with patch.dict(os.environ, {"FABRIC_AGENTIC_TEST_ROOT": "/opt/agentic"}, clear=False):
            path = expand_path("$FABRIC_AGENTIC_TEST_ROOT/profile.json")

        self.assertNotIn("$", str(path))

    def test_falls_back_to_the_home_directory_when_the_variable_is_absent(self) -> None:
        environment = {key: value for key, value in os.environ.items() if key != "USERPROFILE"}
        with patch.dict(os.environ, environment, clear=True):
            path = expand_path("%USERPROFILE%/.fabric-agentic/key.pem")

        self.assertNotIn("%USERPROFILE%", str(path))
        self.assertTrue(str(path).startswith(str(Path.home())))

    def test_keeps_an_unknown_variable_literal(self) -> None:
        environment = {key: value for key, value in os.environ.items() if key != "FABRIC_AGENTIC_ABSENT"}
        with patch.dict(os.environ, environment, clear=True):
            path = expand_path("%FABRIC_AGENTIC_ABSENT%/profile.json")

        self.assertIn("%FABRIC_AGENTIC_ABSENT%", str(path))


if __name__ == "__main__":
    unittest.main()
