import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.review_dispatcher import (
    ReviewDispatcherConfig,
    ReviewDispatcherError,
    PullRequestCandidate,
    review_candidates,
    run_once,
    session_lock,
    load_config,
)


class ReviewDispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ReviewDispatcherConfig(
            github_owner="o",
            github_repository="r",
            github_app_id=1,
            github_installation_id=2,
            github_private_key_path=Path("review.pem"),
            repository_path=Path("repository"),
            claude_command="claude",
            publisher_path=Path("scripts/review_vote_publish.py"),
        )

    @patch("scripts.review_dispatcher.pull_request_reviews")
    @patch("scripts.review_dispatcher.open_pull_requests")
    def test_candidates_ignore_drafts_and_reviewed_heads(self, open_pull_requests, pull_request_reviews) -> None:
        open_pull_requests.return_value = [
            {"number": 1, "draft": True, "head": {"sha": "draft"}},
            {"number": 2, "draft": False, "head": {"sha": "reviewed"}, "title": "old"},
            {"number": 3, "draft": False, "head": {"sha": "new"}, "title": "new", "html_url": "url"},
        ]
        pull_request_reviews.side_effect = [
            [{"commit_id": "reviewed", "user": {"login": "review[bot]"}}],
            [],
        ]

        candidates = review_candidates(self.config, "token", "review[bot]")

        self.assertEqual(candidates, [PullRequestCandidate(3, "new", "new", "url")])

    @patch("scripts.review_dispatcher.discover_once")
    def test_dry_run_does_not_create_task_or_lock(self, discover_once) -> None:
        discover_once.return_value = [{"pull_request": 3, "head_sha": "new"}]
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            tasks_path = Path(directory) / "tasks"

            tasks = run_once(self.config, state_path, tasks_path, dry_run=True)

            self.assertEqual(tasks[0]["pull_request"], 3)
            self.assertFalse(state_path.with_suffix(".lock").exists())
            self.assertFalse(tasks_path.exists())

    @patch("scripts.review_dispatcher.discover_once")
    def test_state_suppresses_a_previously_published_head(self, discover_once) -> None:
        discover_once.return_value = [{"pull_request": 3, "head_sha": "new"}]
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state_path.write_text(json.dumps({"reviewed_heads": {"3": "new"}}), encoding="utf-8")

            tasks = run_once(self.config, state_path, Path(directory) / "tasks", dry_run=True)

        self.assertEqual(tasks, [])

    def test_lock_rejects_a_second_active_session(self) -> None:
        with TemporaryDirectory() as directory:
            lock_path = Path(directory) / "review.lock"
            with session_lock(lock_path):
                with self.assertRaisesRegex(ReviewDispatcherError, "already active"):
                    with session_lock(lock_path):
                        pass

            self.assertFalse(lock_path.exists())

    def test_load_config_expands_windows_environment_paths(self) -> None:
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text(json.dumps({
                "github": {
                    "owner": "o",
                    "repository": "r",
                    "app_id": 1,
                    "installation_id": 2,
                    "private_key_path": "%USERPROFILE%/.fabric-agentic/review.pem",
                },
                "agent": {
                    "repository_path": "%USERPROFILE%/.fabric-agentic/repository",
                    "claude_command": "claude",
                    "publisher_path": "scripts/review_vote_publish.py",
                },
            }), encoding="utf-8")

            config = load_config(config_path)

        self.assertNotIn("%USERPROFILE%", str(config.repository_path))
        self.assertNotIn("%USERPROFILE%", str(config.github_private_key_path))


if __name__ == "__main__":
    unittest.main()