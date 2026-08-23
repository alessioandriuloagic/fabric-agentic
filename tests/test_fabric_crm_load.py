import unittest
import json
from pathlib import Path
from unittest.mock import Mock, patch

from jsonschema import Draft202012Validator, FormatChecker

from scripts.fabric_crm_load import run_load


class FabricCrmLoadTests(unittest.TestCase):
    @patch("scripts.fabric_crm_load.access_token", return_value="opaque-token")
    @patch("scripts.fabric_crm_load.find_workspace", return_value={"id": "workspace-id"})
    @patch("scripts.fabric_crm_load.FabricClient")
    def test_deploys_and_runs_deterministic_load_artifacts(self, client_class: Mock, find_workspace: Mock, access_token: Mock) -> None:
        client = client_class.return_value
        client.ensure_item.side_effect = [
            {"id": "lakehouse-id"},
            {"id": "notebook-id"},
        ]
        client.update_item_definition.return_value = None

        result = run_load(6)

        self.assertEqual(result["rail"], "run_load")
        self.assertEqual(result["outcome"], "success")
        schema = json.loads(Path("schemas/rail-result-v1.0.json").read_text(encoding="utf-8"))
        self.assertEqual(list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(result)), [])
        client.run_notebook.assert_called_once_with("workspace-id", "notebook-id")
        client.update_item_definition.assert_called_once()
        self.assertEqual(client.ensure_item.call_args_list[0].args[1:3], ("lh_bronze_crm_demo", "Lakehouse"))
        self.assertEqual(client.ensure_item.call_args_list[1].args[1:3], ("nb_crm_load", "Notebook"))
        self.assertTrue(Path("fabric/notebook/nb_crm_load.Notebook/notebook-content.py").exists())


if __name__ == "__main__":
    unittest.main()