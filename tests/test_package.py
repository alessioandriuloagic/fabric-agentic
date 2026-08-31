import unittest
from pathlib import Path

import fabric_agentic


PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "fabric_agentic"
PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


class PackageTests(unittest.TestCase):
    def test_the_package_exposes_a_version(self) -> None:
        self.assertTrue(fabric_agentic.__version__)

    def test_the_declared_version_matches_the_package(self) -> None:
        declared = [
            line.split("=", 1)[1].strip().strip('"')
            for line in PYPROJECT.read_text(encoding="utf-8").splitlines()
            if line.startswith("version =")
        ]

        self.assertEqual(declared, [fabric_agentic.__version__])

    def test_the_core_modules_are_importable_without_installation(self) -> None:
        from fabric_agentic import (  # noqa: F401
            agent_session,
            config_paths,
            credential_broker,
            github_app_auth,
            instance_profile,
        )

    def test_the_core_never_imports_the_operational_scripts(self) -> None:
        offenders = [
            path.name
            for path in PACKAGE_ROOT.glob("*.py")
            if "from scripts" in path.read_text(encoding="utf-8")
            or "import scripts" in path.read_text(encoding="utf-8")
        ]

        self.assertEqual(offenders, [], "the reusable core must not depend on operational scripts")


if __name__ == "__main__":
    unittest.main()
