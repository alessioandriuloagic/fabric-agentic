import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from fabric_agentic.cli import main
from fabric_agentic.instance_profile import parse_profile
from fabric_agentic.render import build_plan, render


TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "profiles" / "template" / "instance.json"

PROFILE = {
    "schema_version": "1.0",
    "project": {"slug": "agentic", "display_name": "Fabric Agentic"},
    "tracker": {"type": "github_issues", "owner": "example-org", "repository": "example-repo"},
    "environments": ["dev", "test"],
    "sources": [
        {
            "name": "crm_demo",
            "connector": "crm_dataverse",
            "connection_ref": "fabric-connection://crm-demo",
            "datasets": [
                {
                    "name": "accounts",
                    "primary_key": ["accountid"],
                    "load_mode": "incremental",
                    "watermark_column": "modifiedon",
                }
            ],
        },
        {
            "name": "pagamenti",
            "connector": "file",
            "connection_ref": "fabric-connection://drop",
            "datasets": [{"name": "pagamenti", "primary_key": ["ID_Pagamento"], "load_mode": "full"}],
        },
    ],
    "credentials": [{"name": "execution_credential", "store": "key_vault", "reference": "kv://vault/execution"}],
}


def write_profile(directory: Path, document: dict | None = None) -> Path:
    profile_path = directory / "instance.json"
    profile_path.write_text(json.dumps(document or PROFILE), encoding="utf-8")
    return profile_path


class PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = build_plan(parse_profile(PROFILE))

    def test_derives_one_workspace_per_environment(self) -> None:
        self.assertEqual(
            self.plan["workspaces"],
            [
                {"environment": "dev", "name": "ws_agentic_dev"},
                {"environment": "test", "name": "ws_agentic_test"},
            ],
        )

    def test_states_the_feature_workspace_pattern_without_a_concrete_work_item(self) -> None:
        self.assertEqual(self.plan["feature_workspace_pattern"], "ws_agentic_feature_wi<work-item>")

    def test_carries_the_connector_capabilities_from_the_registry(self) -> None:
        capabilities = {source["name"]: source["capabilities"] for source in self.plan["sources"]}

        self.assertTrue(capabilities["crm_demo"]["supports_incremental"])
        self.assertFalse(capabilities["pagamenti"]["supports_incremental"])

    def test_carries_credential_references_only(self) -> None:
        self.assertEqual(
            self.plan["credentials"],
            [{"name": "execution_credential", "store": "key_vault", "reference": "kv://vault/execution"}],
        )


class RenderTests(unittest.TestCase):
    def render_bytes(self, directory: Path) -> dict[str, bytes]:
        paths = render(parse_profile(PROFILE), directory)
        return {path.name: path.read_bytes() for path in paths}

    def test_renders_the_plan_and_the_summary(self) -> None:
        with TemporaryDirectory() as directory:
            rendered = self.render_bytes(Path(directory))

            self.assertEqual(sorted(rendered), ["README.md", "plan.json"])

    def test_renders_the_same_profile_byte_for_byte(self) -> None:
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            self.assertEqual(self.render_bytes(Path(first)), self.render_bytes(Path(second)))

    def test_rerendering_over_an_existing_output_is_stable(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)

            self.assertEqual(self.render_bytes(output), self.render_bytes(output))

    def test_the_summary_names_every_dataset(self) -> None:
        with TemporaryDirectory() as directory:
            summary = self.render_bytes(Path(directory))["README.md"].decode("utf-8")

            self.assertIn("accounts", summary)
            self.assertIn("pagamenti", summary)
            self.assertIn("modifiedon", summary)


class CommandTests(unittest.TestCase):
    def run_command(self, arguments: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(arguments)
        return code, output.getvalue()

    def test_validate_accepts_the_shipped_template(self) -> None:
        code, output = self.run_command(["validate", "--config", str(TEMPLATE_PATH)])

        self.assertEqual(code, 0)
        self.assertIn("profilo valido", output)

    def test_validate_rejects_an_invalid_profile_before_touching_anything_else(self) -> None:
        with TemporaryDirectory() as directory:
            broken = dict(PROFILE, environments=[])
            profile_path = write_profile(Path(directory), broken)

            code, output = self.run_command(["validate", "--config", str(profile_path)])

        self.assertEqual(code, 1)
        self.assertIn("profilo non valido", output)

    def test_render_writes_the_plan(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = write_profile(root)

            code, _ = self.run_command(["render", "--config", str(profile_path), "--output", str(root / "out")])

            self.assertEqual(code, 0)
            self.assertTrue((root / "out" / "plan.json").is_file())

    def test_render_refuses_an_invalid_profile_and_writes_nothing(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = write_profile(root, dict(PROFILE, environments=[]))
            output = root / "out"

            code, _ = self.run_command(["render", "--config", str(profile_path), "--output", str(output)])

            self.assertEqual(code, 1)
            self.assertFalse(output.exists())

    def test_doctor_fails_when_the_profile_is_invalid(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = write_profile(root, dict(PROFILE, environments=[]))

            code, _ = self.run_command(["--home", directory, "doctor", "--config", str(profile_path)])

            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
