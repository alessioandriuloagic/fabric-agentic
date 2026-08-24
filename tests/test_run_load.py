import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from jsonschema import Draft202012Validator, FormatChecker

from scripts.crm_load import extract_accounts
from scripts.run_load import execute_load


class RunLoadTests(unittest.TestCase):
    def test_publishes_schema_compatible_success_result(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            extract_accounts(
                [{"accountid": "a1", "name": "A", "modifiedon": "2026-08-21T14:00:00Z"}],
                root / "staged.jsonl",
                "run-4",
                datetime(2026, 8, 21, 14, tzinfo=timezone.utc),
            )
            result = execute_load("workspace-1", root / "staged.jsonl", root / "bronze.jsonl", root / "audit.jsonl", root / "watermark.json", "run-4")
            schema = __import__("json").loads(Path("schemas/rail-result-v1.3.json").read_text(encoding="utf-8"))

            errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(result))
            self.assertEqual(errors, [])
            self.assertEqual(result["datasets"][0]["loaded_count"], 1)
            self.assertEqual(result["datasets"][0]["total_destination_count"], 1)
            self.assertEqual(result["datasets"][0]["reconciliation"], "passed")
            self.assertEqual(result["watermark"], "2026-08-21T14:00:00Z")


if __name__ == "__main__":
    unittest.main()