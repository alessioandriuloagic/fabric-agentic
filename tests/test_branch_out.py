import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.branch_out import derive_names, ensure_owner, new_result, require_uuid


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


if __name__ == "__main__":
    unittest.main()