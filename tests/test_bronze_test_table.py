import base64
import json
import unittest
from pathlib import Path

from scripts.bronze_test_table import (
    BRONZE_TABLE,
    COLUMNS,
    BronzeTestTableError,
    plan_creation,
)
from scripts.fabric_artifacts import notebook_definition


NOTEBOOK_PATH = Path("fabric/notebook/nb_create_bronze_test.Notebook")


def notebook_source() -> str:
    return (NOTEBOOK_PATH / "notebook-content.py").read_text(encoding="utf-8")


class BronzeTestTableContractTests(unittest.TestCase):
    def test_declares_exactly_one_string_column(self) -> None:
        self.assertEqual(COLUMNS, (("name", "string", True),))

    def test_first_run_creates_the_table(self) -> None:
        plan = plan_creation()

        self.assertEqual(plan.status, "created")
        self.assertEqual(plan.columns, COLUMNS)

    def test_second_run_leaves_the_existing_table_untouched(self) -> None:
        first = plan_creation()
        second = plan_creation(first.columns)

        self.assertEqual(second.status, "already_exists")
        self.assertEqual(second.columns, first.columns)

    def test_rejects_a_table_that_gained_a_column(self) -> None:
        with self.assertRaises(BronzeTestTableError):
            plan_creation((("name", "string", True), ("_meta_ingested_at", "timestamp", True)))

    def test_rejects_a_table_whose_column_was_retyped(self) -> None:
        with self.assertRaises(BronzeTestTableError):
            plan_creation((("name", "int", True),))

    def test_rejects_a_table_whose_column_was_renamed(self) -> None:
        with self.assertRaises(BronzeTestTableError):
            plan_creation((("nome", "string", True),))

    def test_rejects_a_table_whose_column_changed_nullability(self) -> None:
        with self.assertRaises(BronzeTestTableError):
            plan_creation((("name", "string", False),))


class BronzeTestNotebookArtifactTests(unittest.TestCase):
    def test_builds_a_json_notebook_with_cells_and_language_metadata(self) -> None:
        definition = notebook_definition(
            NOTEBOOK_PATH,
            {"id": "lakehouse-id", "displayName": "lh_bronze_crm_demo", "workspace_id": "workspace-id"},
        )

        self.assertEqual(definition["format"], "ipynb")
        notebook = json.loads(base64.b64decode(definition["parts"][0]["payload"]).decode("utf-8"))
        self.assertEqual(len(notebook["cells"]), 2)
        self.assertEqual(notebook["metadata"]["language_info"]["name"], "python")
        self.assertEqual(
            notebook["metadata"]["dependencies"]["lakehouse"]["default_lakehouse_name"],
            "lh_bronze_crm_demo",
        )

    def test_notebook_declares_the_same_contract_as_the_runtime(self) -> None:
        source = notebook_source()
        declared = [line for line in source.splitlines() if line.strip().startswith("StructField(")]

        self.assertEqual(len(declared), len(COLUMNS))
        self.assertIn('StructField("name", StringType(), True)', declared[0])
        self.assertIn(f'BRONZE_TABLE = "{BRONZE_TABLE}"', source)

    def test_notebook_writes_only_when_the_table_is_missing(self) -> None:
        source = notebook_source()

        self.assertIn("spark.catalog.tableExists(BRONZE_TABLE)", source)
        self.assertEqual(source.count("saveAsTable"), 1)
        self.assertNotIn('mode("overwrite")', source)
        self.assertNotIn("DeltaTable", source)

    def test_notebook_carries_no_secret(self) -> None:
        source = notebook_source()

        self.assertNotIn("getSecret", source)
        self.assertNotIn("client_secret", source)
        self.assertNotIn("vault.azure.net", source)

    def test_notebook_adds_no_metadata_or_pagamenti_column(self) -> None:
        source = notebook_source()

        self.assertNotIn("_meta_", source)
        self.assertNotIn("pagamenti", source)
        self.assertNotIn("ID_Pagamento", source)


if __name__ == "__main__":
    unittest.main()
