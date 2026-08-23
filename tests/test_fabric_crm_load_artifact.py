import unittest
from pathlib import Path

from scripts.fabric_artifacts import notebook_definition


class FabricCrmLoadArtifactTests(unittest.TestCase):
    def test_load_notebook_is_fabric_source_and_preserves_load_order(self) -> None:
        directory = Path("fabric/notebook/nb_crm_load.Notebook")
        definition = notebook_definition(directory)
        source = (directory / "notebook-content.py").read_text(encoding="utf-8")

        self.assertEqual(definition["format"], "ipynb")
        self.assertLess(source.index("write_staging"), source.index("load_bronze"))
        self.assertLess(source.index("audit_delta"), source.index("watermark.write"))
        self.assertIn("modifiedon ge", source)
        self.assertIn("primary key check failed", source)
        self.assertIn("notebookutils.credentials.getSecret", source)
        self.assertNotIn("connections.getCredential", source)


if __name__ == "__main__":
    unittest.main()