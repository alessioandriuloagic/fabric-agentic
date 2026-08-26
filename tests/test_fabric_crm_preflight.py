import unittest
from pathlib import Path
from unittest.mock import Mock

from scripts.fabric_crm_preflight import FabricClient, FabricPreflightError, feature_workspace_name


class FabricCrmPreflightTests(unittest.TestCase):
    def test_workflow_runs_the_deployer_as_a_module(self) -> None:
        workflow = Path(".github/workflows/pipe_agent_crm_preflight.yml").read_text(encoding="utf-8")

        self.assertIn("python -m scripts.fabric_crm_preflight", workflow)
        self.assertIn("Ensure preflight result exists", workflow)

    def test_derives_deterministic_feature_workspace_name(self) -> None:
        self.assertEqual(feature_workspace_name(42), "ws_agentic_feature_wi42")
        with self.assertRaises(FabricPreflightError):
            feature_workspace_name(0)

    def test_ensure_item_reuses_exact_existing_item(self) -> None:
        client = Mock(spec=FabricClient)
        client.list_items.return_value = [{"id": "lakehouse-id", "displayName": "lh_bronze_crm_demo"}]

        result = FabricClient.ensure_item(client, "workspace-id", "lh_bronze_crm_demo", "Lakehouse")

        self.assertEqual(result["id"], "lakehouse-id")
        client.request.assert_not_called()

    def test_ensure_item_rejects_duplicate_item_names(self) -> None:
        client = Mock(spec=FabricClient)
        client.list_items.return_value = [{"id": "one", "displayName": "nb_crm_preflight"}, {"id": "two", "displayName": "nb_crm_preflight"}]

        with self.assertRaises(FabricPreflightError):
            FabricClient.ensure_item(client, "workspace-id", "nb_crm_preflight", "Notebook")

    def test_run_notebook_uses_the_run_notebook_job_type(self) -> None:
        client = Mock(spec=FabricClient)
        client.request.return_value = (202, {"Location": "https://api.fabric.microsoft.com/v1/operations/test"}, {})

        FabricClient.run_notebook(client, "workspace-id", "notebook-id")

        client.request.assert_called_once_with("POST", "/workspaces/workspace-id/items/notebook-id/jobs/instances?jobType=RunNotebook")
        client.wait_lro.assert_called_once_with("https://api.fabric.microsoft.com/v1/operations/test")


if __name__ == "__main__":
    unittest.main()
