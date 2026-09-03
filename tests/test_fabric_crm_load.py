import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from jsonschema import Draft202012Validator, FormatChecker

from scripts.fabric_crm_load import read_load_result, run_load


class FabricCrmLoadTests(unittest.TestCase):
    @patch("scripts.fabric_crm_load.storage_access_token", return_value="opaque-token")
    @patch("scripts.fabric_crm_load.urlopen")
    def test_retries_the_same_per_run_evidence_until_onelake_is_consistent(self, urlopen_mock: Mock, _) -> None:
        missing = __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
            "https://onelake.dfs.fabric.microsoft.com/test",
            404,
            "Not Found",
            None,
            None,
        )
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"rail":"run_load","outcome":"success","run_id":"submitted-run"}'
        urlopen_mock.side_effect = [missing, response]

        with patch("scripts.fabric_crm_load.time.sleep"):
            result = read_load_result("workspace-id", "lakehouse-id", "submitted-run", "storage-token")

        self.assertEqual(result["run_id"], "submitted-run")
        self.assertEqual(urlopen_mock.call_count, 2)

    @patch("scripts.fabric_crm_load.uuid.uuid4", return_value=Mock(hex="submitted-run"))
    @patch("scripts.fabric_crm_load.access_token", return_value="opaque-token")
    @patch("scripts.fabric_crm_load.storage_access_token", return_value="storage-token")
    @patch("scripts.fabric_crm_load.read_load_result")
    @patch("scripts.fabric_crm_load.find_workspace", return_value={"id": "workspace-id"})
    @patch("scripts.fabric_crm_load.FabricClient")
    def test_deploys_and_runs_deterministic_load_artifacts(self, client_class: Mock, find_workspace: Mock, read_load_result: Mock, access_token: Mock, storage_access_token: Mock, _) -> None:
        client = client_class.return_value
        client.ensure_item.side_effect = [
            ({"id": "lakehouse-id"}, False),  # Lakehouse exists (not new)
            ({"id": "notebook-id"}, True),    # Notebook is new
        ]
        client.run_notebook.return_value = "https://api.fabric.microsoft.com/v1/operations/test"
        read_load_result.return_value = {
            "rail": "run_load",
            "outcome": "success",
            "run_id": "20260823T153000Z-abcd1234",
            "loaded_count": 5,
            "total_destination_count": 10,
            "reconciliation": "passed",
            "watermark": "2026-08-23T15:30:00Z",
        }

        result = run_load(6)

        self.assertEqual(result["rail"], "run_load")
        self.assertEqual(result["outcome"], "success")
        self.assertEqual(result["run_id"], "submitted-run")
        self.assertEqual(result["datasets"][0]["loaded_count"], 5)
        self.assertEqual(result["datasets"][0]["total_destination_count"], 10)
        self.assertNotEqual(result["datasets"][0]["loaded_count"], result["datasets"][0]["total_destination_count"])
        self.assertEqual(result["watermark"], "2026-08-23T15:30:00Z")
        schema = json.loads(Path("schemas/rail-result-v1.3.json").read_text(encoding="utf-8"))
        self.assertEqual(list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(result)), [])
        client.run_notebook.assert_called_once_with(
            "workspace-id",
            "notebook-id",
            {"run_id": "submitted-run"},
            wait=False,
        )
        storage_access_token.assert_called_once_with()
        client.wait_lro.assert_called_once_with("https://api.fabric.microsoft.com/v1/operations/test", "notebook run")
        read_load_result.assert_called_once_with("workspace-id", "lakehouse-id", "submitted-run", "storage-token")
        self.assertEqual(client.ensure_item.call_args_list[0].args[1:3], ("lh_bronze_crm_demo", "Lakehouse"))
        self.assertEqual(client.ensure_item.call_args_list[1].args[1:3], ("nb_crm_load", "Notebook"))
        self.assertTrue(Path("fabric/notebook/nb_crm_load.Notebook/notebook-content.py").exists())

    @patch("scripts.fabric_crm_load.access_token", return_value="opaque-token")
    @patch("scripts.fabric_crm_load.storage_access_token", return_value="storage-token")
    @patch("scripts.fabric_crm_load.read_load_result")
    @patch("scripts.fabric_crm_load.find_workspace", return_value={"id": "workspace-id"})
    @patch("scripts.fabric_crm_load.FabricClient")
    @patch("scripts.fabric_crm_load.uuid.uuid4", return_value=Mock(hex="submitted-run"))
    def test_publishes_quality_failure_from_correlated_reconciliation_evidence(self, _, client_class: Mock, find_workspace: Mock, read_load_result: Mock, storage_access_token: Mock, access_token: Mock) -> None:
        client = client_class.return_value
        client.ensure_item.side_effect = [({"id": "lakehouse-id"}, False), ({"id": "notebook-id"}, True)]
        read_load_result.return_value = {
            "rail": "run_load",
            "outcome": "quality_failure",
            "run_id": "submitted-run",
            "loaded_count": 9,
            "total_destination_count": 10,
            "reconciliation": "failed",
            "watermark": "2026-08-23T15:30:00Z",
        }

        result = run_load(6)

        self.assertEqual(result["outcome"], "quality_failure")
        self.assertEqual(result["datasets"][0]["status"], "failed")
        self.assertEqual(result["datasets"][0]["reconciliation"], "failed")


if __name__ == "__main__":
    unittest.main()