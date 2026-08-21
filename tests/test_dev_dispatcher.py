import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.dev_dispatcher import AzureDevOpsClient, DispatcherConfig, human_reply_tasks, launch_smoke_session, review_thread_tasks, run_once, run_polling, run_smoke, smoke_comment


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

    @patch("scripts.dev_dispatcher.run_once", return_value=[])
    def test_polling_writes_safe_metadata_once_per_cycle(self, _) -> None:
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "dispatcher.log"
            run_polling(self.config, Path(directory) / "state.json", Path(directory) / "tasks", log_path, cycles=2, sleep=lambda _: None)
            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual([event["event"] for event in events], ["poll_completed", "poll_completed"])
        self.assertTrue(all("token" not in json.dumps(event).lower() for event in events))

    @patch("scripts.dev_dispatcher.subprocess.run")
    def test_smoke_session_returns_only_structured_documents(self, run_mock) -> None:
        run_mock.return_value.returncode = 0
        run_mock.return_value.stdout = json.dumps({"structured_output": {"documents_read": ["CONTEXT.md", "AGENTS.md"]}})

        documents = launch_smoke_session(self.config, Path("task.json"))

        self.assertEqual(documents, ["CONTEXT.md", "AGENTS.md"])
        self.assertIn("Read", run_mock.call_args.args[0])

    def test_smoke_comment_identifies_the_dev_agent(self) -> None:
        comment = smoke_comment(["CONTEXT.md", "AGENTS.md"])

        self.assertIn("[fabric-agentic-dev-agent]", comment)
        self.assertIn("- CONTEXT.md", comment)

    @patch("scripts.dev_dispatcher.launch_smoke_session", return_value=["CONTEXT.md"])
    @patch("scripts.dev_dispatcher.refresh_clone")
    @patch("scripts.dev_dispatcher.AzureDevOpsClient")
    def test_smoke_moves_ticket_to_doing_before_session_and_done_after(self, client_mock, _, __) -> None:
        with TemporaryDirectory() as directory:
            run_smoke(self.config, 42, Path(directory))

        client = client_mock.return_value
        self.assertEqual(client.method_calls[0].args, (42, "Doing"))
        self.assertEqual(client.method_calls[-1].args, (42, "Done"))

    @patch("scripts.dev_dispatcher.urlopen")
    def test_work_item_patch_operations_use_json_patch_content_type(self, urlopen_mock) -> None:
        urlopen_mock.return_value.__enter__.return_value.read.return_value = b"{}"
        client = AzureDevOpsClient(self.config, token_provider=lambda _: "token")

        client.request("POST", "/_apis/wit/workitems/$Issue?api-version=7.1", [{"op": "add"}])

        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.get_header("Content-type"), "application/json-patch+json")


if __name__ == "__main__":
    unittest.main()