import argparse
import json
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from scripts.crm_load import LoadResult, extract_accounts
from scripts.run_load import execute_load, main


RUN_LOAD_SCHEMA = json.loads(Path("schemas/rail-result-v1.3.json").read_text(encoding="utf-8"))
WORKFLOW_PATH = Path(".github/workflows/pipe_agent_crm_run_load.yml")


def schema_errors(result: dict) -> list:
    return list(Draft202012Validator(RUN_LOAD_SCHEMA, format_checker=FormatChecker()).iter_errors(result))


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

            self.assertEqual(schema_errors(result), [])
            self.assertEqual(result["datasets"][0]["loaded_count"], 1)
            self.assertEqual(result["datasets"][0]["total_destination_count"], 1)
            self.assertEqual(result["datasets"][0]["reconciliation"], "passed")
            self.assertEqual(result["watermark"], "2026-08-21T14:00:00Z")

    def test_fails_reconciliation_when_staged_count_differs_from_extracted_count(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch(
                "scripts.run_load.load_staged_accounts",
                return_value=LoadResult("run-6", extracted_count=2, loaded_count=1, destination_count=10, committed_watermark=None),
            ):
                result = execute_load("workspace-1", root / "staged.jsonl", root / "bronze.jsonl", root / "audit.jsonl", root / "watermark.json", "run-6")

            self.assertEqual(result["datasets"][0]["reconciliation"], "failed")

    def test_publishes_schema_compatible_quality_failure_result(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "staged.jsonl").write_text(
                '{"accountid":"a1","name":"One","modifiedon":"2026-08-21T14:00:00Z"}\n'
                '{"accountid":"a1","name":"Two","modifiedon":"2026-08-21T14:01:00Z"}\n',
                encoding="utf-8",
            )
            arguments = argparse.Namespace(
                workspace_id="workspace-1",
                staged=root / "staged.jsonl",
                bronze=root / "bronze.jsonl",
                audit=root / "audit.jsonl",
                watermark=root / "watermark.json",
                run_id="run-5",
                output=root / "rail-result.json",
            )

            with patch("scripts.run_load.parse_args", return_value=arguments):
                exit_code = main()
            result = json.loads((root / "rail-result.json").read_text(encoding="utf-8"))

            self.assertEqual(exit_code, 1)
            self.assertEqual(result["outcome"], "quality_failure")
            self.assertEqual(result["datasets"][0]["pk_check"], "failed")
            self.assertEqual(schema_errors(result), [])
            self.assertFalse((root / "bronze.jsonl").exists())

    def test_unresolved_workspace_still_publishes_a_valid_failure_result(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            arguments = argparse.Namespace(
                workspace_id="",
                staged=root / "staged.jsonl",
                bronze=root / "bronze.jsonl",
                audit=root / "audit.jsonl",
                watermark=root / "watermark.json",
                run_id="",
                output=root / "rail-result.json",
            )

            with patch("scripts.run_load.parse_args", return_value=arguments):
                exit_code = main()
            result = json.loads((root / "rail-result.json").read_text(encoding="utf-8"))

            self.assertEqual(exit_code, 1)
            self.assertEqual(result["outcome"], "technical_failure")
            self.assertEqual(schema_errors(result), [])

    def test_workflow_fallback_result_matches_the_run_load_contract(self) -> None:
        template = re.search(r"printf '(\{.*\})\\n'", WORKFLOW_PATH.read_text(encoding="utf-8")).group(1)
        fallback = json.loads(
            template.replace("crm-load-wi%s", "crm-load-wi158").replace('"%s"', '"2026-09-01T10:00:00Z"')
        )

        self.assertEqual(schema_errors(fallback), [])
        self.assertEqual(fallback["outcome"], "technical_failure")


if __name__ == "__main__":
    unittest.main()
