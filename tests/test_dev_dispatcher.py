import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.dev_dispatcher import DispatcherConfig, run_once


class DevDispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = DispatcherConfig(
            organization="AlessioAndriuloDev",
            project="fabric-agentic",
            tenant_domain="agicdev.onmicrosoft.com",
            ado_app_id="app-id",
            certificate_thumbprint="thumbprint",
            github_owner="alessioandriuloagic",
            github_repository="fabric-agentic",
            github_app_id="4672750",
            github_installation_id="155470382",
            github_private_key_path=Path("key.pem"),
            repository_path=Path("repository"),
            claude_command="claude",
            poll_seconds=30,
        )

    @patch("scripts.dev_dispatcher.AzureDevOpsClient.new_work_item_ids", return_value=[6, 7])
    def test_dry_run_returns_only_undispatched_new_work(self, _) -> None:
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state_path.write_text(json.dumps({"dispatched_work_items": [6]}), encoding="utf-8")

            tasks = run_once(self.config, state_path, Path(directory) / "tasks", dry_run=True)

        self.assertEqual([task["work_item_id"] for task in tasks], [7])
        self.assertEqual(tasks[0]["trigger"], "new_work")

    @patch("scripts.dev_dispatcher.launch_session", return_value=True)
    @patch("scripts.dev_dispatcher.refresh_clone")
    @patch("scripts.dev_dispatcher.AzureDevOpsClient.new_work_item_ids", return_value=[6, 7])
    def test_dispatches_one_task_and_persists_it_before_launch(self, _, __, ___) -> None:
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            tasks = run_once(self.config, state_path, Path(directory) / "tasks", dry_run=False)
            state = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual([task["work_item_id"] for task in tasks], [6])
        self.assertEqual(state["dispatched_work_items"], [6])


if __name__ == "__main__":
    unittest.main()