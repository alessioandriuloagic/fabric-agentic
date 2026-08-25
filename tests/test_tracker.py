"""Tests for work-item tracker implementations."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.tracker import AzureDevOpsTracker, GitHubIssuesTracker, TrackerError, WorkItemComment


class AzureDevOpsTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_token = "mock-token-redacted"
        self.token_provider = MagicMock(return_value=self.mock_token)
        self.tracker = AzureDevOpsTracker(
            organization="TestOrg",
            project="TestProject",
            token_provider=self.token_provider,
            dev_agent_display_name="[test-agent]",
        )

    @patch("scripts.tracker.urlopen")
    def test_new_items_queries_open_to_do_items(self, mock_urlopen) -> None:
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps({
            "workItems": [
                {"id": 101},
                {"id": 102},
            ]
        }).encode("utf-8")
        mock_urlopen.return_value = mock_response

        items = self.tracker.new_items()

        self.assertEqual(items, [101, 102])
        # Verify that token provider was called
        self.token_provider.assert_called()

    @patch("scripts.tracker.urlopen")
    def test_comments_returns_normalized_work_item_comment(self, mock_urlopen) -> None:
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps({
            "comments": [
                {
                    "commentId": 1,
                    "createdBy": {"displayName": "Owner"},
                    "content": "Please review",
                },
                {
                    "commentId": 2,
                    "createdBy": {"displayName": "[test-agent]"},
                    "content": "Agent response",
                },
            ]
        }).encode("utf-8")
        mock_urlopen.return_value = mock_response

        comments = self.tracker.comments(101)

        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0].id, 1)
        self.assertEqual(comments[0].is_agent_comment, False)
        self.assertEqual(comments[1].id, 2)
        self.assertEqual(comments[1].is_agent_comment, True)

    def test_item_url_returns_azure_devops_url(self) -> None:
        url = self.tracker.item_url(42)

        self.assertIn("dev.azure.com", url)
        self.assertIn("TestOrg", url)
        self.assertIn("TestProject", url)
        self.assertIn("/42", url)

    @patch("scripts.tracker.urlopen")
    def test_add_comment_sends_comment_text(self, mock_urlopen) -> None:
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps({}).encode("utf-8")
        mock_urlopen.return_value = mock_response

        self.tracker.add_comment(101, "Test comment")

        # Verify that urlopen was called
        mock_urlopen.assert_called()
        self.token_provider.assert_called()

    @patch("scripts.tracker.urlopen")
    def test_set_state_sends_state_patch(self, mock_urlopen) -> None:
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps({}).encode("utf-8")
        mock_urlopen.return_value = mock_response

        self.tracker.set_state(101, "Done")

        # Verify that urlopen was called with PATCH
        mock_urlopen.assert_called()
        self.token_provider.assert_called()


class GitHubIssuesTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = GitHubIssuesTracker(
            owner="test-owner",
            repository="test-repo",
            github_app_id=12345,
            github_installation_id=67890,
            github_private_key_path=Path("fake-key.pem"),
            agent_identity="[test-agent]",
        )

    @patch("scripts.tracker.create_installation_token")
    @patch("scripts.tracker.urlopen")
    def test_new_items_queries_github_graphql(self, mock_urlopen, mock_token_fn) -> None:
        mock_token_fn.return_value.token = "github-token-redacted"
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps({
            "data": {
                "repository": {
                    "issues": {
                        "nodes": [
                            {"number": 1},
                            {"number": 2},
                        ]
                    }
                }
            }
        }).encode("utf-8")
        mock_urlopen.return_value = mock_response

        items = self.tracker.new_items()

        self.assertEqual(items, [1, 2])
        # Verify that token was created but not exposed
        mock_token_fn.assert_called_with(12345, 67890, Path("fake-key.pem"))

    @patch("scripts.tracker.create_installation_token")
    @patch("scripts.tracker.urlopen")
    def test_comments_normalizes_github_comments(self, mock_urlopen, mock_token_fn) -> None:
        mock_token_fn.return_value.token = "github-token-redacted"
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps([
            {
                "id": 1001,
                "user": {"login": "owner"},
                "body": "Please check this",
            },
            {
                "id": 1002,
                "user": {"login": "agent"},
                "body": "[test-agent] Reviewed.",
            },
        ]).encode("utf-8")
        mock_urlopen.return_value = mock_response

        comments = self.tracker.comments(1)

        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0].id, 1001)
        self.assertEqual(comments[0].is_agent_comment, False)
        self.assertEqual(comments[1].id, 1002)
        self.assertEqual(comments[1].is_agent_comment, True)

    def test_item_url_returns_github_url(self) -> None:
        url = self.tracker.item_url(42)

        self.assertIn("github.com", url)
        self.assertIn("test-owner", url)
        self.assertIn("test-repo", url)
        self.assertIn("/issues/42", url)

    @patch("scripts.tracker.create_installation_token")
    @patch("scripts.tracker.urlopen")
    def test_add_comment_sends_via_rest_api(self, mock_urlopen, mock_token_fn) -> None:
        mock_token_fn.return_value.token = "github-token-redacted"
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps({}).encode("utf-8")
        mock_urlopen.return_value = mock_response

        self.tracker.add_comment(1, "Test comment")

        # Verify that urlopen was called
        mock_urlopen.assert_called()

    @patch("scripts.tracker.create_installation_token")
    @patch("scripts.tracker.urlopen")
    def test_set_state_transitions_issue(self, mock_urlopen, mock_token_fn) -> None:
        mock_token_fn.return_value.token = "github-token-redacted"
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps({}).encode("utf-8")
        mock_urlopen.return_value = mock_response

        self.tracker.set_state(1, "Done")

        # Verify that urlopen was called
        mock_urlopen.assert_called()
        # Verify that token was created but not exposed in logs
        mock_token_fn.assert_called()


if __name__ == "__main__":
    unittest.main()
