import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.branch_out import (
    RailError,
    classify_failure_code,
    derive_names,
    ensure_git_connection,
    ensure_owner,
    ensure_workspace,
    main,
    new_result,
    require_uuid,
)


class BranchOutTests(unittest.TestCase):
    def test_derives_deterministic_names(self) -> None:
        self.assertEqual(
            derive_names(42, "onboard-open-meteo"),
            ("feature/wi-42-onboard-open-meteo", "ws_agentic_feature_wi42"),
        )

    def test_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            derive_names(0, "onboard-open-meteo")
        with self.assertRaises(ValueError):
            derive_names(42, "Unsafe slug")
        with self.assertRaises(ValueError):
            require_uuid("FABRIC_CAPACITY_ID", "not-a-uuid")

    def test_failure_result_is_structured_without_workspace(self) -> None:
        result = new_result(42, "feature/wi-42-onboard-open-meteo", "ws_agentic_feature_wi42")

        self.assertEqual(result["outcome"], "technical_failure")
        self.assertIsNone(result["workspace_id"])
        self.assertEqual(result["datasets"], [])
        self.assertEqual(result["branch_out"]["sync_status"], "not_synchronized")
        self.assertIsNone(result["branch_out"]["failure_stage"])
        self.assertIsNone(result["branch_out"]["failure_code"])

    def test_classifies_forbidden_api_error_without_exposing_its_message(self) -> None:
        self.assertEqual(classify_failure_code("ERROR: (Forbidden) Request denied"), "forbidden")

    @patch("scripts.branch_out.fabric")
    def test_existing_owner_is_not_added_twice(self, fabric_mock) -> None:
        fabric_mock.return_value = {
            "value": [{"principal": {"id": "owner-id"}, "role": "Admin"}]
        }

        ensure_owner("workspace-id", "owner-id")

        fabric_mock.assert_called_once_with("GET", "/workspaces/workspace-id/roleAssignments")

    def test_workflow_is_limited_to_dev_without_target_environment_input(self) -> None:
        workflow = Path(".github/workflows/branch-out.yml").read_text(encoding="utf-8")

        self.assertIn("environment: dev", workflow)
        self.assertIn("vars.FABRIC_DEPLOY_CLIENT_ID", workflow)
        self.assertIn("vars.FABRIC_DEPLOY_TENANT_ID", workflow)
        self.assertNotIn("vars.AZURE_CLIENT_ID", workflow)
        self.assertNotIn("target_environment", workflow)
        self.assertNotIn("environment:", workflow.replace("environment: dev", ""))

    @patch("scripts.branch_out.execute", side_effect=RailError("workspace"))
    @patch("scripts.branch_out.parse_args")
    def test_workspace_failure_is_reported_in_result(self, parse_args_mock, _) -> None:
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "rail-result.json"
            parse_args_mock.return_value.work_item_id = 6
            parse_args_mock.return_value.slug = "smoke-branch-out"
            parse_args_mock.return_value.output = output_path

            self.assertEqual(main(), 1)
            result = __import__("json").loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result["branch_out"]["failure_stage"], "workspace")

    @patch.dict(
        "os.environ",
        {
            "FABRIC_GIT_CONNECTION_ID": "connection-id",
            "FABRIC_GIT_ORGANIZATION": "alessioandriuloagic",
            "FABRIC_GIT_REPOSITORY": "fabric-agentic",
        },
    )
    @patch("scripts.branch_out.fabric_optional", return_value={"gitProviderDetails": None})
    @patch("scripts.branch_out.fabric")
    def test_partial_git_connection_is_connected(self, fabric_mock, _) -> None:
        connection_created = ensure_git_connection("workspace-id", "feature/wi-6-smoke-branch-out")

        self.assertTrue(connection_created)
        self.assertEqual(fabric_mock.call_args.args[:2], ("POST", "/workspaces/workspace-id/git/connect"))

    @patch("scripts.branch_out.find_workspace", return_value={"id": "workspace-id", "capacityId": None})
    @patch("scripts.branch_out.fabric")
    def test_existing_workspace_without_capacity_is_assigned(self, fabric_mock, _) -> None:
        workspace_id, status = ensure_workspace("ws_agentic_feature_wi6", "capacity-id")

        self.assertEqual((workspace_id, status), ("workspace-id", "existing"))
        fabric_mock.assert_called_once_with(
            "POST",
            "/workspaces/workspace-id/assignToCapacity",
            {"capacityId": "capacity-id"},
        )


if __name__ == "__main__":
    unittest.main()