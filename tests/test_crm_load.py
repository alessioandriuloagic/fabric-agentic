import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.crm_load import CrmLoadError, extract_accounts, load_staged_accounts


class CrmLoadTests(unittest.TestCase):
    def test_extracts_inclusive_delta_to_staging(self) -> None:
        with TemporaryDirectory() as directory:
            staging = Path(directory) / "run.jsonl"
            result = extract_accounts(
                [
                    {"accountid": "a1", "name": "Old", "modifiedon": "2026-08-21T13:00:00Z"},
                    {"accountid": "a2", "name": "At boundary", "modifiedon": "2026-08-21T14:00:00Z"},
                ],
                staging,
                "run-1",
                datetime(2026, 8, 21, 14, tzinfo=timezone.utc),
            )

            self.assertEqual(result.extracted_count, 1)
            self.assertEqual(json.loads(staging.read_text(encoding="utf-8"))["accountid"], "a2")

    def test_merges_idempotently_and_commits_audit_before_watermark(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            staging = root / "staged.jsonl"
            bronze = root / "bronze.jsonl"
            audit = root / "audit.jsonl"
            watermark = root / "watermark.json"
            bronze.write_text('{"accountid":"a1","name":"Old","modifiedon":"2026-08-21T13:00:00Z"}\n', encoding="utf-8")
            extract_accounts(
                [{"accountid": "a1", "name": "Updated", "modifiedon": "2026-08-21T14:00:00Z"}],
                staging,
                "run-2",
            )

            first = load_staged_accounts(staging, bronze, audit, watermark, "run-2")
            second = load_staged_accounts(staging, bronze, audit, watermark, "run-2")

            self.assertEqual(first.destination_count, 1)
            self.assertEqual(second.destination_count, 1)
            self.assertEqual(json.loads(bronze.read_text(encoding="utf-8"))["name"], "Updated")
            self.assertEqual(len(audit.read_text(encoding="utf-8").splitlines()), 1)
            self.assertEqual(json.loads(watermark.read_text(encoding="utf-8"))["confirmed_watermark"], "2026-08-21T14:00:00Z")

    def test_rejects_duplicate_keys_before_writing_bronze(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            staging = root / "staged.jsonl"
            bronze = root / "bronze.jsonl"
            extract_accounts(
                [
                    {"accountid": "a1", "name": "One", "modifiedon": "2026-08-21T14:00:00Z"},
                    {"accountid": "a1", "name": "Two", "modifiedon": "2026-08-21T14:01:00Z"},
                ],
                staging,
                "run-3",
            )

            with self.assertRaises(CrmLoadError):
                load_staged_accounts(staging, bronze, root / "audit.jsonl", root / "watermark.json", "run-3")
            self.assertFalse(bronze.exists())


if __name__ == "__main__":
    unittest.main()