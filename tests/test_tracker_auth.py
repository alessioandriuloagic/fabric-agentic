import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.tracker_auth import TrackerAuthError, azure_user_token, github_user_credentials
from fabric_agentic import credential_helper
from scripts import dev_dispatcher, issue_dispatcher, review_dispatcher


class TrackerAuthTests(unittest.TestCase):
    def test_model_wrapper_blocks_credential_export_before_requesting_token(self):
        with patch("sys.argv", ["helper", "gh", "gh.exe", "auth", "token"]), patch.object(
            credential_helper, "request_token"
        ) as provider:
            self.assertEqual(credential_helper.main(), 1)
        provider.assert_not_called()

    def test_azure_user_token_verifies_separate_tenant_and_account(self):
        tenant = "11111111-1111-4111-8111-111111111111"
        responses = [subprocess.CompletedProcess([], 0, json.dumps(payload), "") for payload in (
            {"tenantId": tenant, "user": {"type": "user", "name": "colleague@example.com"}},
            {"accessToken": "private-ado-token"},
        )]
        with patch("scripts.tracker_auth.shutil.which", return_value="az.cmd"), patch(
            "scripts.tracker_auth.subprocess.run", side_effect=responses
        ) as command:
            self.assertEqual(azure_user_token("colleague@example.com", tenant, Path("ado-context")), "private-ado-token")
        self.assertIn("https://app.vssps.visualstudio.com", command.call_args.args[0])
        self.assertEqual(command.call_args.kwargs["env"]["AZURE_CONFIG_DIR"], "ado-context")

    def test_azure_wrong_tenant_stops_before_token(self):
        with patch("scripts.tracker_auth.shutil.which", return_value="az.cmd"), patch(
            "scripts.tracker_auth.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, json.dumps({"tenantId": "other"}), ""),
        ) as command:
            with self.assertRaisesRegex(TrackerAuthError, "tracker_tenant_mismatch"):
                azure_user_token("colleague", "expected", Path("ado-context"))
        self.assertEqual(command.call_count, 1)

    def test_issue_and_review_discovery_use_the_verified_user(self):
        authentication = {"mode": "github_user", "account": "colleague", "config_directory": "user-context"}
        for dispatcher, candidates in (
            (issue_dispatcher, "intake_candidates"), (review_dispatcher, "review_candidates"),
        ):
            with self.subTest(dispatcher=dispatcher.__name__):
                config_class = dispatcher.IssueDispatcherConfig if dispatcher is issue_dispatcher else dispatcher.ReviewDispatcherConfig
                config = config_class("customer", "project", 0, 0, Path(), Path("clone"), "claude", tracker_auth=authentication)
                with patch.object(dispatcher, "github_user_credentials", return_value=("user-token", "colleague")), patch.object(
                    dispatcher, "create_installation_token"
                ) as app_token, patch.object(dispatcher, candidates, return_value=[]) as discover:
                    self.assertEqual(dispatcher.discover_once(config), [])
                app_token.assert_not_called()
                discover.assert_called_once_with(config, "user-token", "colleague")

    def test_all_github_dispatchers_accept_user_auth_without_app_fields(self):
        document = {
            "github": {"owner": "customer", "repository": "project", "authentication": {
                "mode": "github_user", "account": "colleague", "config_directory": "user-context",
            }},
            "agent": {"repository_path": "isolated-clone", "claude_command": "claude", "poll_seconds": 30},
            "dispatcher": {"tracker_type": "github_issues"},
        }
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "dispatcher.json"
            config_path.write_text(json.dumps(document), encoding="utf-8")
            for dispatcher in (dev_dispatcher, issue_dispatcher, review_dispatcher):
                with self.subTest(dispatcher=dispatcher.__name__):
                    config = dispatcher.load_config(config_path)
                    self.assertEqual(config.tracker_auth["mode"], "github_user")

    def test_user_credentials_verify_login_without_echoing_token(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({"login": "colleague"}).encode()
        with patch("scripts.tracker_auth.shutil.which", return_value="gh.exe"), patch(
            "scripts.tracker_auth.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, "private-token\n", "private-error"),
        ), patch("scripts.tracker_auth.urlopen", return_value=response):
            token, login = github_user_credentials("colleague", Path("user-context"))
        self.assertEqual(login, "colleague")
        self.assertEqual(token, "private-token")

    def test_wrong_user_is_rejected_without_echoing_response(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({"login": "other"}).encode()
        with patch("scripts.tracker_auth.shutil.which", return_value="gh.exe"), patch(
            "scripts.tracker_auth.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, "private-token", ""),
        ), patch("scripts.tracker_auth.urlopen", return_value=response):
            with self.assertRaises(TrackerAuthError) as failure:
                github_user_credentials("colleague", Path("user-context"))
        self.assertEqual(str(failure.exception), "tracker_account_mismatch")


if __name__ == "__main__":
    unittest.main()