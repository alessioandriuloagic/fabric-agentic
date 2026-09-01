import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from fabric_agentic.bootstrap import (
    CHECKLIST_FILE_NAME,
    INSTANCE_FILE_NAME,
    InitError,
    init,
    slug_from_directory,
)
from fabric_agentic.cli import main
from fabric_agentic.instance_profile import parse_profile


class SlugFromDirectoryTests(unittest.TestCase):
    def test_lowercases_and_replaces_invalid_characters(self) -> None:
        self.assertEqual(slug_from_directory(Path("Cliente ACME S.p.A.")), "cliente_acme_s_p_a")

    def test_prefixes_a_slug_that_would_not_start_with_a_letter(self) -> None:
        self.assertEqual(slug_from_directory(Path("42-rockets")), "p_42_rockets")

    def test_falls_back_to_a_generic_slug_when_the_name_has_no_usable_characters(self) -> None:
        self.assertEqual(slug_from_directory(Path("___")), "project")


class InitTests(unittest.TestCase):
    def test_writes_a_profile_that_validates(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "cliente"

            result = init(root, project_slug="cliente_acme", display_name="Cliente ACME")

            self.assertEqual({path.name for path in result.written}, {INSTANCE_FILE_NAME, CHECKLIST_FILE_NAME})
            self.assertEqual(result.skipped, ())
            document = json.loads((root / INSTANCE_FILE_NAME).read_text(encoding="utf-8"))
            profile = parse_profile(document)
            self.assertEqual(profile.project_slug, "cliente_acme")
            self.assertEqual(profile.display_name, "Cliente ACME")

    def test_derives_the_slug_from_the_directory_when_not_given(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "Cliente Nuovo"

            init(root)

            document = json.loads((root / INSTANCE_FILE_NAME).read_text(encoding="utf-8"))
            self.assertEqual(document["project"]["slug"], "cliente_nuovo")

    def test_the_checklist_names_the_project_and_points_at_the_onboarding_doc(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)

            init(root, project_slug="cliente_acme", display_name="Cliente ACME")

            checklist = (root / CHECKLIST_FILE_NAME).read_text(encoding="utf-8")
            self.assertIn("Cliente ACME", checklist)
            self.assertIn("cliente_acme", checklist)
            self.assertIn("docs/functional/06-onboarding-nuovo-cliente.md", checklist)

    def test_no_secret_is_generated(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)

            init(root, project_slug="cliente_acme")

            instance_text = (root / INSTANCE_FILE_NAME).read_text(encoding="utf-8")
            checklist_text = (root / CHECKLIST_FILE_NAME).read_text(encoding="utf-8")
            for text in (instance_text, checklist_text):
                self.assertNotIn("client_secret", text.lower().replace(" ", ""))
                self.assertIn("REPLACE_WITH", instance_text)

    def test_rerunning_is_idempotent_and_does_not_overwrite(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            init(root, project_slug="cliente_acme")
            (root / INSTANCE_FILE_NAME).write_text("edited-by-colleague", encoding="utf-8")

            result = init(root, project_slug="cliente_acme")

            self.assertEqual(result.written, ())
            self.assertEqual({path.name for path in result.skipped}, {INSTANCE_FILE_NAME, CHECKLIST_FILE_NAME})
            self.assertEqual((root / INSTANCE_FILE_NAME).read_text(encoding="utf-8"), "edited-by-colleague")

    def test_force_regenerates_existing_files(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            init(root, project_slug="cliente_acme")
            (root / INSTANCE_FILE_NAME).write_text("edited-by-colleague", encoding="utf-8")

            result = init(root, project_slug="cliente_acme", force=True)

            self.assertEqual({path.name for path in result.written}, {INSTANCE_FILE_NAME, CHECKLIST_FILE_NAME})
            self.assertNotEqual((root / INSTANCE_FILE_NAME).read_text(encoding="utf-8"), "edited-by-colleague")

    def test_refuses_an_invalid_slug_before_writing_anything(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "cliente"

            with self.assertRaises(InitError):
                init(root, project_slug="Not A Slug!")

            self.assertFalse(root.exists())


class InitCommandTests(unittest.TestCase):
    def run_command(self, arguments: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(arguments)
        return code, output.getvalue()

    def test_init_creates_a_starter_verifiable_by_validate_and_doctor(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "cliente"

            code, output = self.run_command(
                ["init", "--directory", str(root), "--project-slug", "cliente_acme"]
            )

            self.assertEqual(code, 0)
            self.assertIn(str(root / "instance.json"), output)

            code, _ = self.run_command(["validate", "--config", str(root / "instance.json")])
            self.assertEqual(code, 0)

            code, _ = self.run_command(
                ["--home", directory, "doctor", "--config", str(root / "instance.json")]
            )
            self.assertEqual(code, 1)  # doctor still fails: no agent is provisioned on a clean machine

    def test_init_rejects_an_invalid_slug(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "cliente"

            code, output = self.run_command(
                ["init", "--directory", str(root), "--project-slug", "Not A Slug!"]
            )

            self.assertEqual(code, 1)
            self.assertIn("init non riuscito", output)


if __name__ == "__main__":
    unittest.main()
