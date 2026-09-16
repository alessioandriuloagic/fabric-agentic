import base64
import json
import re
import unittest
from pathlib import Path

from scripts.demo_alessio_table import (
    COLUMNS,
    LAKEHOUSE,
    ROWS,
    TABLE,
    DemoAlessioTableError,
    plan_load,
)
from scripts.fabric_artifacts import notebook_definition


NOTEBOOK_PATH = Path("fabric/notebook/nb_demo_alessio.Notebook")
LAKEHOUSE_PATH = Path("fabric/lakehouse/lh_demo.Lakehouse")
BRONZE_TEST_NOTEBOOK_PATH = Path("fabric/notebook/nb_create_bronze_test.Notebook")


def notebook_source() -> str:
    return (NOTEBOOK_PATH / "notebook-content.py").read_text(encoding="utf-8")


def logical_id(artifact_directory: Path) -> str:
    platform = json.loads((artifact_directory / ".platform").read_text(encoding="utf-8"))
    return platform["config"]["logicalId"]


class DemoAlessioTableContractTests(unittest.TestCase):
    def test_declares_exactly_one_string_column(self) -> None:
        self.assertEqual(COLUMNS, (("names", "string", True),))

    def test_declares_exactly_one_literal_row(self) -> None:
        self.assertEqual(ROWS, ({"names": "alessio"},))

    def test_first_run_creates_the_table_with_the_declared_row(self) -> None:
        plan = plan_load()

        self.assertEqual(plan.status, "created")
        self.assertEqual(plan.columns, COLUMNS)
        self.assertEqual(plan.rows_to_write, ROWS)

    def test_second_run_rewrites_the_same_row(self) -> None:
        first = plan_load()
        second = plan_load(first.columns)

        self.assertEqual(second.status, "overwritten")
        self.assertEqual(second.columns, first.columns)
        self.assertEqual(second.rows_to_write, ROWS)

    def test_rejects_a_table_that_gained_a_column(self) -> None:
        with self.assertRaises(DemoAlessioTableError):
            plan_load((("names", "string", True), ("_meta_ingested_at", "timestamp", True)))

    def test_rejects_a_table_whose_column_was_retyped(self) -> None:
        with self.assertRaises(DemoAlessioTableError):
            plan_load((("names", "int", True),))

    def test_rejects_a_table_whose_column_was_renamed(self) -> None:
        with self.assertRaises(DemoAlessioTableError):
            plan_load((("name", "string", True),))

    def test_rejects_a_table_whose_column_changed_nullability(self) -> None:
        with self.assertRaises(DemoAlessioTableError):
            plan_load((("names", "string", False),))


class DemoAlessioNotebookArtifactTests(unittest.TestCase):
    def test_notebook_declares_the_same_contract_as_the_runtime(self) -> None:
        source = notebook_source()
        declared = [line for line in source.splitlines() if line.strip().startswith("StructField(")]

        self.assertEqual(len(declared), len(COLUMNS))
        self.assertIn('StructField("names", StringType(), True)', declared[0])
        self.assertIn(f'TABLE = "{TABLE}"', source)
        self.assertIn(f'LAKEHOUSE = "{LAKEHOUSE}"', source)

    def test_notebook_loads_the_same_literal_row_as_the_runtime(self) -> None:
        source = notebook_source()

        self.assertIn(json.dumps(dict(ROWS[0])), source)
        self.assertEqual(source.count('"alessio"'), 1)

    def test_notebook_rewrites_the_row_without_altering_the_schema(self) -> None:
        source = notebook_source()

        self.assertEqual(source.count('mode("overwrite")'), 1)
        self.assertIn("check_no_implicit_change", source)
        self.assertNotIn("overwriteSchema", source)
        self.assertNotIn("DeltaTable", source)

    def test_notebook_does_not_depend_on_a_default_lakehouse(self) -> None:
        source = notebook_source()

        self.assertIn('notebookutils.runtime.context["currentWorkspaceId"]', source)
        self.assertIn("abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com", source)
        self.assertNotIn("spark.catalog", source)
        self.assertNotIn("saveAsTable", source)

    def test_notebook_carries_no_secret_and_no_hardcoded_identifier(self) -> None:
        source = notebook_source()

        self.assertNotIn("getSecret", source)
        self.assertNotIn("client_secret", source)
        self.assertNotIn("vault.azure.net", source)
        self.assertNotIn("connection_id", source)
        self.assertIsNone(re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-", source))

    def test_notebook_adds_no_technical_metadata_column(self) -> None:
        source = notebook_source()

        self.assertNotIn("_meta_", source)

    def test_platform_metadata_names_the_approved_notebook(self) -> None:
        platform = json.loads((NOTEBOOK_PATH / ".platform").read_text(encoding="utf-8"))

        self.assertEqual(platform["metadata"]["type"], "Notebook")
        self.assertEqual(platform["metadata"]["displayName"], "nb_demo_alessio")

    def test_builds_a_notebook_payload_without_a_default_lakehouse(self) -> None:
        definition = notebook_definition(NOTEBOOK_PATH)

        self.assertEqual(definition["format"], "ipynb")
        notebook = json.loads(base64.b64decode(definition["parts"][0]["payload"]).decode("utf-8"))
        self.assertEqual(len(notebook["cells"]), 2)
        self.assertNotIn("dependencies", notebook["metadata"])


class DemoLakehouseArtifactTests(unittest.TestCase):
    def test_lakehouse_is_versioned_with_its_platform_metadata(self) -> None:
        platform = json.loads((LAKEHOUSE_PATH / ".platform").read_text(encoding="utf-8"))

        self.assertEqual(platform["metadata"]["type"], "Lakehouse")
        self.assertEqual(platform["metadata"]["displayName"], LAKEHOUSE)

    def test_lakehouse_definition_carries_valid_metadata(self) -> None:
        metadata = json.loads((LAKEHOUSE_PATH / "lakehouse.metadata.json").read_text(encoding="utf-8"))

        self.assertEqual(metadata, {})

    def test_every_versioned_artifact_has_its_own_logical_id(self) -> None:
        # A copied logicalId makes two Git items claim to be the same workspace item.
        identifiers = [
            logical_id(LAKEHOUSE_PATH),
            logical_id(NOTEBOOK_PATH),
            logical_id(BRONZE_TEST_NOTEBOOK_PATH),
        ]

        self.assertEqual(len(set(identifiers)), len(identifiers))


if __name__ == "__main__":
    unittest.main()
