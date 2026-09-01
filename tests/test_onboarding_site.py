import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fabric_agentic.instance_profile import parse_profile
from scripts.build_onboarding_site import ASSET_NAMES, build


class OnboardingSiteTests(unittest.TestCase):
    def test_build_writes_static_assets_schema_and_valid_starter(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)

            paths = build(output)

            self.assertEqual(
                {path.name for path in paths},
                {*ASSET_NAMES, "instance-profile-v1.0.json", "starter-instance.json"},
            )
            starter = json.loads((output / "starter-instance.json").read_text(encoding="utf-8"))
            self.assertEqual(parse_profile(starter).project_slug, "cliente_demo")

    def test_build_is_reproducible_byte_for_byte(self) -> None:
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            first_output = Path(first)
            second_output = Path(second)

            build(first_output)
            build(second_output)

            self.assertEqual(
                {path.name: path.read_bytes() for path in first_output.iterdir()},
                {path.name: path.read_bytes() for path in second_output.iterdir()},
            )

    def test_page_loads_the_generated_contract_and_has_no_external_runtime_dependency(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            build(output)

            html = (output / "index.html").read_text(encoding="utf-8")
            javascript = (output / "app.js").read_text(encoding="utf-8")

            self.assertIn('src="app.js"', html)
            self.assertIn('href="styles.css"', html)
            self.assertIn('fetch("instance-profile-v1.0.json")', javascript)
            self.assertNotIn("https://cdn", html + javascript)

    def test_generated_files_never_contain_secret_values(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            build(output)

            starter = (output / "starter-instance.json").read_text(encoding="utf-8")
            self.assertIn("REPLACE_WITH_SECRET_REFERENCE", starter)
            self.assertNotIn('"client_secret"', starter)


if __name__ == "__main__":
    unittest.main()