import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from scripts.issue_dispatcher import (
    IssueDispatcherConfig,
    IssueDispatcherError,
    IntakeCandidate,
    intake_candidates,
    launch_issue_session,
    load_config,
    prepare_issue_clone,
    publisher_command,
    run_once,
    session_lock,
)


class IssueDispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = IssueDispatcherConfig(
            github_owner="o",
            github_repository="r",
            github_app_id=3,
            github_installation_id=4,
            github_private_key_path=Path("issue.pem"),
            repository_path=Path("repository"),
            claude_command="claude",
        )

    @patch("scripts.issue_dispatcher.subprocess.run")
    def test_session_decodes_claude_output_as_utf8(self, run_mock) -> None:
        run_mock.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"structured_output": {"work_package": "pacchetto"}}),
        )

        self.assertEqual(launch_issue_session(self.config, Path("task.json")), "pacchetto")
        self.assertIn("--json-schema", run_mock.call_args.args[0])
        self.assertEqual(run_mock.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run_mock.call_args.kwargs["errors"], "replace")

    @patch("scripts.issue_dispatcher.subprocess.run")
    def test_schema_validated_package_survives_auxiliary_error_status(self, run_mock) -> None:
        run_mock.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "is_error": True,
                "stop_reason": "max_turns",
                "structured_output": {"work_package": "pacchetto completo"},
            }),
        )

        self.assertEqual(launch_issue_session(self.config, Path("task.json")), "pacchetto completo")

    @patch("scripts.issue_dispatcher.issue_comments")
    @patch("scripts.issue_dispatcher.open_intake_issues")
    def test_candidates_skip_packaged_and_approved_intakes(self, open_intake_issues, issue_comments) -> None:
        open_intake_issues.return_value = [
            {"number": 10, "title": "already packaged", "body": "b", "labels": [{"name": "issue-agent"}]},
            {"number": 11, "title": "approved", "body": "b", "labels": [{"name": "issue-agent"}, {"name": "dev-agent"}]},
            {"number": 12, "title": "new intake", "body": "b", "labels": [{"name": "issue-agent"}], "html_url": "url"},
        ]
        issue_comments.side_effect = [
            [{"body": "[fabric-agentic-issue-agent] package abc", "user": {"login": "issue[bot]"}}],
            [{"body": "a human note", "user": {"login": "owner"}}],
        ]

        candidates = intake_candidates(self.config, "token", "issue[bot]")

        self.assertEqual(candidates, [IntakeCandidate(12, "new intake", "b", "url")])

    @patch("scripts.issue_dispatcher.discover_once")
    def test_dry_run_creates_no_task_state_or_lock(self, discover_once) -> None:
        discover_once.return_value = [{"issue": 12, "title": "new intake"}]
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            tasks_path = Path(directory) / "tasks"

            tasks = run_once(self.config, state_path, tasks_path, dry_run=True)

            self.assertEqual(tasks[0]["issue"], 12)
            self.assertFalse(state_path.exists())
            self.assertFalse(state_path.with_suffix(".lock").exists())
            self.assertFalse(tasks_path.exists())

    @patch("scripts.issue_dispatcher.discover_once")
    def test_state_suppresses_an_already_dispatched_intake(self, discover_once) -> None:
        discover_once.return_value = [{"issue": 12, "title": "new intake"}]
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state_path.write_text(json.dumps({"dispatched_intakes": [12]}), encoding="utf-8")

            tasks = run_once(self.config, state_path, Path(directory) / "tasks", dry_run=True)

        self.assertEqual(tasks, [])

    def test_publisher_is_invoked_as_a_module(self) -> None:
        command = publisher_command(self.config, {"issue": 12}, Path("package.txt"))

        self.assertEqual(command[1], "-m")
        self.assertEqual(command[2], "scripts.issue_package_publish")
        self.assertEqual(command[command.index("--issue") + 1], "12")

    @patch("scripts.issue_dispatcher.create_installation_token")
    @patch("scripts.issue_dispatcher.subprocess.run")
    def test_clone_is_prepared_on_main(self, mock_run, mock_token) -> None:
        mock_token.return_value.token = "installation-token"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        prepare_issue_clone(self.config)

        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(["git", "-C", "repository", "fetch", "--prune", "origin", "main"], commands)
        self.assertIn(["git", "-C", "repository", "merge", "--ff-only", "origin/main"], commands)

    @patch("scripts.issue_dispatcher.create_installation_token")
    @patch("scripts.issue_dispatcher.subprocess.run")
    def test_clone_preparation_uses_the_brokered_credential(self, mock_run, mock_token) -> None:
        mock_token.return_value.token = "installation-token"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        prepare_issue_clone(self.config)

        environment = mock_run.call_args.kwargs["env"]
        self.assertIn("FABRIC_AGENT_CREDENTIAL_BROKER", environment)
        self.assertNotIn("GH_TOKEN", environment)
        self.assertNotIn("installation-token", json.dumps(environment))

    def test_lock_rejects_a_second_active_session(self) -> None:
        with TemporaryDirectory() as directory:
            lock_path = Path(directory) / "issue.lock"
            with session_lock(lock_path):
                with self.assertRaisesRegex(IssueDispatcherError, "already active"):
                    with session_lock(lock_path):
                        pass

            self.assertFalse(lock_path.exists())

    def test_load_config_expands_windows_environment_paths(self) -> None:
        with TemporaryDirectory() as directory:
            config = load_config(self.write_config(Path(directory), app_id=3, installation_id=4))

        self.assertNotIn("%USERPROFILE%", str(config.repository_path))
        self.assertNotIn("%USERPROFILE%", str(config.github_private_key_path))

    def test_discovery_refuses_an_unprovisioned_identity(self) -> None:
        with TemporaryDirectory() as directory:
            config = load_config(self.write_config(Path(directory), app_id=0, installation_id=0))

            with self.assertRaisesRegex(IssueDispatcherError, "identity is not provisioned"):
                run_once(config, Path(directory) / "state.json", Path(directory) / "tasks", dry_run=True)

    def write_config(self, directory: Path, app_id: int, installation_id: int) -> Path:
        config_path = directory / f"config-{app_id}.json"
        config_path.write_text(json.dumps({
            "github": {
                "owner": "o",
                "repository": "r",
                "app_id": app_id,
                "installation_id": installation_id,
                "private_key_path": "%USERPROFILE%/.fabric-agentic/issue.pem",
            },
            "agent": {
                "repository_path": "%USERPROFILE%/.fabric-agentic/repository",
                "claude_command": "claude",
            },
        }), encoding="utf-8")
        return config_path


if __name__ == "__main__":
    unittest.main()
