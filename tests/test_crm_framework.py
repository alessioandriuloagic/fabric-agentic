import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.crm_framework import CrmFrameworkError, build_accounts_request, commit_watermark, load_configuration, plan_accounts_load


class CrmFrameworkTests(unittest.TestCase):
    def test_loads_the_committed_crm_tracer_configuration(self) -> None:
        configuration = load_configuration(Path("configuration/crm_demo.json"))

        self.assertEqual(configuration["source_system"], "crm_demo")
        self.assertEqual(configuration["datasets"][0]["primary_key"], ["accountid"])

    def test_rejects_configuration_missing_the_incremental_watermark(self) -> None:
        configuration = json.loads(Path("configuration/crm_demo.json").read_text(encoding="utf-8"))
        del configuration["datasets"][0]["watermark_column"]

        with TemporaryDirectory() as directory:
            configuration_path = Path(directory) / "crm_demo.json"
            configuration_path.write_text(json.dumps(configuration), encoding="utf-8")
            with self.assertRaises(CrmFrameworkError):
                load_configuration(configuration_path)

    def test_builds_full_and_incremental_accounts_requests(self) -> None:
        full_request = build_accounts_request("https://org4009cd0e.crm4.dynamics.com", None)
        incremental_request = build_accounts_request(
            "https://org4009cd0e.crm4.dynamics.com/",
            datetime(2026, 8, 21, 14, 0, tzinfo=timezone.utc),
        )

        self.assertIn("/api/data/v9.2/accounts", full_request)
        self.assertNotIn("$filter", full_request)
        self.assertIn("modifiedon%20ge%202026-08-21T14%3A00%3A00Z", incremental_request)

    def test_rejects_naive_watermarks(self) -> None:
        with self.assertRaises(CrmFrameworkError):
            build_accounts_request("https://org4009cd0e.crm4.dynamics.com", datetime(2026, 8, 21, 14, 0))

    def test_inclusive_watermark_is_merged_and_committed_only_after_bronze_and_audit(self) -> None:
        confirmed = datetime(2026, 8, 21, 14, 0, tzinfo=timezone.utc)
        observed = datetime(2026, 8, 21, 15, 0, tzinfo=timezone.utc)
        plan = plan_accounts_load("https://org4009cd0e.crm4.dynamics.com", confirmed, observed)

        self.assertEqual(plan.merge_key, "accountid")
        self.assertIn("modifiedon%20ge%202026-08-21T14%3A00%3A00Z", plan.request_url)
        with self.assertRaises(CrmFrameworkError):
            commit_watermark(plan, bronze_merged=True, audit_written=False)
        self.assertEqual(commit_watermark(plan, bronze_merged=True, audit_written=True), observed)


if __name__ == "__main__":
    unittest.main()
