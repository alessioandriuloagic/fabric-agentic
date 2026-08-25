import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from scripts.dev_dispatcher import DispatcherConfig, human_reply_tasks, launch_smoke_session, load_state, review_thread_tasks, run_once, run_polling, run_smoke, smoke_comment, stage_work_item_context
from scripts.tracker import WorkItemComment


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
    @patch("scripts.dev_dispatcher.create_tracker")
    def test_dry_run_returns_only_undispatched_new_work(self, mock_create_tracker, _, __) -> None:
        mock_tracker = MagicMock()
        mock_tracker.new_items.return_value = [6, 7]
        mock_tracker.item_url.side_effect = lambda item_id: f"https://example.com/item/{item_id}"
        mock_create_tracker.return_value = mock_tracker

        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state_path.write_text(json.dumps({"dispatched_work_items": [6]}), encoding="utf-8")

            tasks = run_once(self.config, state_path, Path(directory) / "tasks", dry_run=True)

        self.assertEqual([task["work_item_id"] for task in tasks], [7])
        self.assertEqual(tasks[0]["trigger"], "new_work")

    @patch("scripts.dev_dispatcher.urlopen")
    def test_stages_issue_context_and_attachment(self, mock_urlopen) -> None:
        mock_tracker = MagicMock()
        mock_tracker.context.return_value = {
            "title": "Call transcript",
            "body": "Transcript",
            "attachments": ["https://github.com/user-attachments/assets/file-1"],
        }
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"attachment-data"
        mock_urlopen.return_value = response

        with TemporaryDirectory() as temp_dir:
            context_path = stage_work_item_context(self.config, mock_tracker, 42, Path(temp_dir))

            self.assertIsNotNone(context_path)
            self.assertIn("Transcript", context_path.read_text(encoding="utf-8"))
            self.assertEqual((context_path.parent / "attachment-1").read_bytes(), b"attachment-data")

    def test_stages_repository_attachments_without_remote_download(self) -> None:
        mock_tracker = MagicMock()
        mock_tracker.context.return_value = {
            "title": "Call transcript",
            "body": "Transcript",
            "attachments": ["https://github.com/user-attachments/files/remote"],
        }

        with TemporaryDirectory() as temp_dir:
            repository_path = Path(temp_dir) / "repository"
            attachment_directory = repository_path / "attachments" / "72"
            attachment_directory.mkdir(parents=True)
            (attachment_directory / "call.txt").write_text("local attachment", encoding="utf-8")
            config = replace(self.config, repository_path=repository_path)

            context_path = stage_work_item_context(config, mock_tracker, 72, Path(temp_dir) / "tasks")

            self.assertIn(str(attachment_directory / "call.txt"), context_path.read_text(encoding="utf-8"))
            mock_tracker.download_attachment.assert_not_called()

    @patch("scripts.dev_dispatcher.github_graphql", return_value={"repository": {"pullRequests": {"nodes": []}}})
    @patch("scripts.dev_dispatcher.human_reply_tasks", return_value=([], set()))
    @patch("scripts.dev_dispatcher.launch_session", return_value=True)
    @patch("scripts.dev_dispatcher.refresh_clone")
    @patch("scripts.dev_dispatcher.create_tracker")
    def test_dispatches_one_task_and_persists_it_before_launch(self, mock_create_tracker, _, __, ___, ____) -> None:
        mock_tracker = MagicMock()
        mock_tracker.new_items.return_value = [6, 7]
        mock_tracker.item_url.side_effect = lambda item_id: f"https://example.com/item/{item_id}"
        mock_create_tracker.return_value = mock_tracker

        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            tasks = run_once(self.config, state_path, Path(directory) / "tasks", dry_run=False)
            state = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual([task["work_item_id"] for task in tasks], [6])
        self.assertEqual(state["dispatched_work_items"], [6])

    @patch("scripts.dev_dispatcher.github_graphql", return_value={"repository": {"pullRequests": {"nodes": []}}})
    @patch("scripts.dev_dispatcher.human_reply_tasks", return_value=([], set()))
    @patch("scripts.dev_dispatcher.launch_session", return_value=False)
    @patch("scripts.dev_dispatcher.refresh_clone")
    @patch("scripts.dev_dispatcher.create_tracker")
    def test_failed_session_raises_after_persisting_dispatch(self, mock_create_tracker, _, __, ___, ____) -> None:
        mock_tracker = MagicMock()
        mock_tracker.new_items.return_value = [6]
        mock_tracker.item_url.return_value = "https://example.com/item/6"
        mock_create_tracker.return_value = mock_tracker

        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            with self.assertRaisesRegex(Exception, "Dev Agent session failed"):
                run_once(self.config, state_path, Path(directory) / "tasks", dry_run=False)
            state = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(state["dispatched_work_items"], [6])

    def test_human_reply_ignores_agent_comments_and_seen_comments(self) -> None:
        mock_tracker = MagicMock()
        mock_tracker.waiting_input_items.return_value = [6]
        mock_tracker.comments.return_value = [
            WorkItemComment(id=1, author="dev-agent", text="...", is_agent_comment=True),
            WorkItemComment(id=2, author="Owner", text="...", is_agent_comment=False),
        ]
        mock_tracker.item_url.return_value = "https://example.com/item/6"

        tasks, seen = human_reply_tasks(self.config, mock_tracker, {1})

        self.assertEqual([task["trigger"] for task in tasks], ["human_reply"])
        self.assertEqual(seen, {1, 2})

    def test_loads_windows_utf8_bom_state_file(self) -> None:
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state_path.write_text('{"dispatched_work_items": [6]}', encoding="utf-8-sig")

            state = load_state(state_path)

        self.assertEqual(state["dispatched_work_items"], [6])

    def test_review_thread_ignores_resolved_and_seen_threads(self) -> None:
        mock_tracker = MagicMock()
        mock_tracker.item_url.return_value = "https://example.com/item/6"
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

        tasks, seen = review_thread_tasks(self.config, mock_tracker, payload, {"seen"})

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
    @patch("scripts.dev_dispatcher.create_tracker")
    def test_smoke_moves_ticket_to_doing_before_session_and_done_after(self, mock_create_tracker, _, __) -> None:
        mock_tracker = MagicMock()
        mock_tracker.item_url.return_value = "https://example.com/item/42"
        mock_create_tracker.return_value = mock_tracker

        with TemporaryDirectory() as directory:
            run_smoke(self.config, 42, Path(directory))

        # Verify that set_state was called with "Doing" first and "Done" last
        calls = [call for call in mock_tracker.method_calls if call[0] == "set_state"]
        self.assertEqual(calls[0].args, (42, "Doing"))
        self.assertEqual(calls[-1].args, (42, "Done"))

if __name__ == "__main__":
    unittest.main()