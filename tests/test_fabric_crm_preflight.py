import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.fabric_crm_preflight import FabricClient, FabricPreflightError, azure_cli_command, feature_workspace_name


class FabricCrmPreflightTests(unittest.TestCase):
    def test_uses_cmd_launcher_for_azure_cli_on_windows(self) -> None:
        with patch("scripts.fabric_crm_preflight.os.name", "nt"):
            self.assertEqual(azure_cli_command(), "az.cmd")

    def test_workflow_runs_the_deployer_as_a_module(self) -> None:
        workflow = Path(".github/workflows/pipe_agent_crm_preflight.yml").read_text(encoding="utf-8")

        self.assertIn("python -m scripts.fabric_crm_preflight", workflow)
        self.assertIn("Ensure preflight result exists", workflow)

    def test_preflight_notebook_uses_configured_dataverse_environment(self) -> None:
        notebook = Path("fabric/notebook/nb_crm_preflight.Notebook/notebook-content.py").read_text(encoding="utf-8")
        configuration = Path("configuration/crm_demo.json").read_text(encoding="utf-8")

        self.assertIn('"https://org12202591.crm4.dynamics.com"', notebook)
        self.assertNotIn("org4009cd0e", notebook)
        self.assertIn('"environment_url": "https://org12202591.crm4.dynamics.com"', configuration)

    def test_preflight_uses_key_vault_credentials_not_unsupported_connections_api(self) -> None:
        notebook = Path("fabric/notebook/nb_crm_preflight.Notebook/notebook-content.py").read_text(encoding="utf-8")

        self.assertIn("notebookutils.credentials.getSecret", notebook)
        self.assertNotIn("notebookutils.connections.getCredential", notebook)

    def test_preflight_uses_the_record_free_dataverse_count_endpoint(self) -> None:
        notebook = Path("fabric/notebook/nb_crm_preflight.Notebook/notebook-content.py").read_text(encoding="utf-8")

        self.assertIn('/api/data/v9.2/accounts/$count', notebook)
        self.assertNotIn("$top=0", notebook)
        self.assertIn('response.content.decode("utf-8-sig")', notebook)

    def test_preflight_binds_and_updates_notebook_default_lakehouse(self) -> None:
        source = Path("scripts/fabric_crm_preflight.py").read_text(encoding="utf-8")

        self.assertIn('"workspace_id": workspace["id"]', source)
        self.assertIn("notebook_definition(\n        NOTEBOOK_DIRECTORY,", source)
        self.assertIn("client.update_item_definition(workspace[\"id\"], notebook[\"id\"], definition)", source)

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
        client.wait_lro.assert_called_once_with(
            "https://api.fabric.microsoft.com/v1/operations/test", "notebook run"
        )

    def test_wait_lro_reports_safe_failure_code(self) -> None:
        client = FabricClient("token", sleep=lambda _: None)
        client.request = Mock(side_effect=[
            (200, {}, {"status": "Failed", "error": {"errorCode": "NotebookRunFailed", "message": "secret"}}),
        ])

        with self.assertRaisesRegex(FabricPreflightError, r"notebook run failed with status Failed \(NotebookRunFailed\)"):
            client.wait_lro("https://api.fabric.microsoft.com/v1/operations/test", "notebook run")


if __name__ == "__main__":
    unittest.main()
