import base64
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.fabric_artifacts import FabricArtifactError, notebook_definition


NOTEBOOK_PATH = Path("fabric/notebook/nb_crm_preflight.Notebook")


class FabricArtifactTests(unittest.TestCase):
    def test_builds_fabric_git_source_notebook_definition(self) -> None:
        definition = notebook_definition(NOTEBOOK_PATH)

        self.assertEqual(definition["format"], "FabricGitSource")
        self.assertEqual([part["path"] for part in definition["parts"]], ["notebook-content.py", ".platform"])
        source = base64.b64decode(definition["parts"][0]["payload"]).decode("utf-8")
        self.assertIn("$top=0&$count=true", source)
        self.assertNotIn("print(access_token)", source)

    def test_rejects_missing_platform_metadata(self) -> None:
        with TemporaryDirectory() as directory:
            notebook = Path(directory)
            (notebook / "notebook-content.py").write_text("# Fabric notebook source\n# CELL ********************\n", encoding="utf-8")

            with self.assertRaises(FabricArtifactError):
                notebook_definition(notebook)


if __name__ == "__main__":
    unittest.main()
