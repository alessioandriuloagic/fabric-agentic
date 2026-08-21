import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.dev_dispatcher import DispatcherConfig, human_reply_tasks, review_thread_tasks, run_once


class DevDispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = DispatcherConfig(
            organization="AlessioAndriuloDev",
            project="fabric-agentic",
            tenant_domain="agicdev.onmicrosoft.com",
            ado_app_id="app-id",
            certificate_thumbprint="thumbprint",
            dev_agent_display_name="fabric-agentic-dev-agent",
            github_owner="alessioandriuloagic",
            github_repository="fabric-agentic",
            github_app_id="4672750",
            github_installation_id="155470382",
            github_private_key_path=Path("key.pem"),
            repository_path=Path("repository"),
            claude_command="claude",
            poll_seconds=30,
        )

    @patch("scripts.dev_dispatcher.github_graphql", return_value={"repository": {"pullRequests": {"nodes": []}}})
    @patch("scripts.dev_dispatcher.human_reply_tasks", return_value=([], set()))
    @patch("scripts.dev_dispatcher.AzureDevOpsClient.new_work_item_ids", return_value=[6, 7])
    def test_dry_run_returns_only_undispatched_new_work(self, _, __, ___) -> None:
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state_path.write_text(json.dumps({"dispatched_work_items": [6]}), encoding="utf-8")

            tasks = run_once(self.config, state_path, Path(directory) / "tasks", dry_run=True)

        self.assertEqual([task["work_item_id"] for task in tasks], [7])
        self.assertEqual(tasks[0]["trigger"], "new_work")

    @patch("scripts.dev_dispatcher.github_graphql", return_value={"repository": {"pullRequests": {"nodes": []}}})
    @patch("scripts.dev_dispatcher.human_reply_tasks", return_value=([], set()))
    @patch("scripts.dev_dispatcher.launch_session", return_value=True)
    @patch("scripts.dev_dispatcher.refresh_clone")
    @patch("scripts.dev_dispatcher.AzureDevOpsClient.new_work_item_ids", return_value=[6, 7])
    def test_dispatches_one_task_and_persists_it_before_launch(self, _, __, ___, ____, _____) -> None:
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            tasks = run_once(self.config, state_path, Path(directory) / "tasks", dry_run=False)
            state = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual([task["work_item_id"] for task in tasks], [6])
        self.assertEqual(state["dispatched_work_items"], [6])

    def test_human_reply_ignores_agent_comments_and_seen_comments(self) -> None:
        class Client:
            def waiting_input_work_item_ids(self):
                return [6]

            def comments(self, _):
                return [
                    {"commentId": 1, "createdBy": {"displayName": "fabric-agentic-dev-agent"}},
                    {"commentId": 2, "createdBy": {"displayName": "Owner"}},
                ]

        tasks, seen = human_reply_tasks(self.config, Client(), {1})

        self.assertEqual([task["trigger"] for task in tasks], ["human_reply"])
        self.assertEqual(seen, {1, 2})

    def test_review_thread_ignores_resolved_and_seen_threads(self) -> None:
        payload = {
            "repository": {"pullRequests": {"nodes": [{
                "url": "https://github.com/alessioandriuloagic/fabric-agentic/pull/1",
                "headRefName": "feature/wi-6-smoke-branch-out",
                "reviewThreads": {"nodes": [
                    {"id": "seen", "isResolved": False},
                    {"id": "resolved", "isResolved": True},
                    {"id": "new", "isResolved": False},
                ]},
            }]}}
        }

        tasks, seen = review_thread_tasks(self.config, payload, {"seen"})

        self.assertEqual([(task["work_item_id"], task["trigger"]) for task in tasks], [(6, "review_thread")])
        self.assertEqual(seen, {"seen", "new"})


if __name__ == "__main__":
    unittest.main()