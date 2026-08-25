import base64
import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.fabric_artifacts import notebook_definition
from scripts.pagamenti_load import (
    BRONZE_TABLE,
    COLUMNS,
    PRIMARY_KEY,
    PagamentiLoadError,
    check_primary_key,
    merge_bronze,
    read_pagamenti,
)


ATTACHMENT = Path("attachments/72/pagamenti.csv")
NOTEBOOK_PATH = Path("fabric/notebook/nb_ingest_pagamenti.Notebook")
HEADER = ",".join(name for name, _ in COLUMNS)


def write_csv(directory: str, *rows: str) -> Path:
    path = Path(directory) / "pagamenti.csv"
    path.write_text("\n".join((HEADER, *rows)) + "\n", encoding="utf-8")
    return path


class PagamentiSourceTests(unittest.TestCase):
    def test_parses_the_attached_source_file_without_errors(self) -> None:
        rows = read_pagamenti(ATTACHMENT)

        self.assertEqual(len(rows), 10)
        self.assertEqual(list(rows[0]), [name for name, _ in COLUMNS])

    def test_types_each_column_according_to_the_declared_schema(self) -> None:
        rows = {row["ID_Pagamento"]: row for row in read_pagamenti(ATTACHMENT)}

        self.assertIsInstance(rows["PAG-0001"]["Data"], date)
        self.assertEqual(rows["PAG-0001"]["Data"], date(2026, 1, 5))
        self.assertIsInstance(rows["PAG-0002"]["Importo"], Decimal)
        self.assertEqual(rows["PAG-0002"]["Importo"], Decimal("3400.50"))

    def test_keeps_optional_columns_null_instead_of_empty_strings(self) -> None:
        rows = {row["ID_Pagamento"]: row for row in read_pagamenti(ATTACHMENT)}

        self.assertIsNone(rows["PAG-0005"]["IBAN"])
        self.assertIsNone(rows["PAG-0004"]["Note"])

    def test_rejects_a_non_numeric_amount(self) -> None:
        with TemporaryDirectory() as directory:
            source = write_csv(directory, "PAG-0001,2026-01-05,Cliente,non-numerico,EUR,Bonifico,Completato,FAT-1,,")

            with self.assertRaises(PagamentiLoadError):
                read_pagamenti(source)

    def test_rejects_an_amount_beyond_the_declared_scale(self) -> None:
        with TemporaryDirectory() as directory:
            source = write_csv(directory, "PAG-0001,2026-01-05,Cliente,1250.005,EUR,Bonifico,Completato,FAT-1,,")

            with self.assertRaises(PagamentiLoadError):
                read_pagamenti(source)

    def test_rejects_a_date_that_is_not_iso(self) -> None:
        with TemporaryDirectory() as directory:
            source = write_csv(directory, "PAG-0001,05/01/2026,Cliente,1250.00,EUR,Bonifico,Completato,FAT-1,,")

            with self.assertRaises(PagamentiLoadError):
                read_pagamenti(source)

    def test_rejects_a_header_that_drifted_from_the_declared_schema(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "pagamenti.csv"
            path.write_text("ID_Pagamento,Data,Importo\nPAG-0001,2026-01-05,1250.00\n", encoding="utf-8")

            with self.assertRaises(PagamentiLoadError):
                read_pagamenti(path)


class PagamentiBronzeMergeTests(unittest.TestCase):
    def test_merges_the_attached_file_without_duplicating_rows_on_rerun(self) -> None:
        rows = read_pagamenti(ATTACHMENT)

        first, first_result = merge_bronze(rows)
        second, second_result = merge_bronze(rows, first)

        self.assertEqual(first_result.destination_count, 10)
        self.assertEqual(second_result.destination_count, 10)
        self.assertEqual(len(second), len(first))
        self.assertEqual(
            sorted(row["ID_Pagamento"] for row in second),
            sorted(row["ID_Pagamento"] for row in first),
        )

    def test_updates_an_existing_key_instead_of_appending_it(self) -> None:
        rows = read_pagamenti(ATTACHMENT)
        stale = [dict(row, Stato="Da aggiornare") for row in rows]

        destination, result = merge_bronze(rows, stale)

        self.assertEqual(result.destination_count, 10)
        self.assertNotIn("Da aggiornare", [row["Stato"] for row in destination])

    def test_rejects_duplicate_primary_keys_before_merging(self) -> None:
        rows = read_pagamenti(ATTACHMENT)
        duplicated = rows + [dict(rows[0])]

        with self.assertRaises(PagamentiLoadError):
            check_primary_key(duplicated)
        with self.assertRaises(PagamentiLoadError):
            merge_bronze(duplicated)

    def test_reports_reconciliation_failure_when_bronze_holds_unknown_keys(self) -> None:
        rows = read_pagamenti(ATTACHMENT)
        orphan = [dict(rows[0], ID_Pagamento="PAG-9999")]

        with self.assertRaises(PagamentiLoadError):
            merge_bronze(rows, orphan)


class PagamentiNotebookArtifactTests(unittest.TestCase):
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
        source = (NOTEBOOK_PATH / "notebook-content.py").read_text(encoding="utf-8")
        declared = [line.split('"')[1] for line in source.splitlines() if line.strip().startswith("StructField(")]

        self.assertEqual(declared, [name for name, _ in COLUMNS])
        self.assertIn(f'PRIMARY_KEY = "{PRIMARY_KEY}"', source)
        self.assertIn(f'BRONZE_TABLE = "{BRONZE_TABLE}"', source)

    def test_notebook_merges_on_the_primary_key_and_carries_no_secret(self) -> None:
        source = (NOTEBOOK_PATH / "notebook-content.py").read_text(encoding="utf-8")

        self.assertIn("whenMatchedUpdateAll()", source)
        self.assertIn('.option("mode", "FAILFAST")', source)
        self.assertNotIn("getSecret", source)
        self.assertNotIn("client_secret", source)


if __name__ == "__main__":
    unittest.main()
