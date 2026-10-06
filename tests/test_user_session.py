import io
import json
import subprocess
import tempfile
import urllib.error
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from fabric_agentic.cli import main
from fabric_agentic.instance_profile import load_profile
from fabric_agentic.render import build_plan
from fabric_agentic.user_session import UserSession, UserSessionError


TENANT = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"


class UserSessionTests(unittest.TestCase):
    def test_init_generates_an_assisted_profile_without_credential_or_crm_placeholders(self):
        with tempfile.TemporaryDirectory() as directory:
            with redirect_stdout(io.StringIO()):
                code = main([
                    "init", "--directory", directory, "--project-slug", "client",
                    "--tenant-id", TENANT, "--workspace-id", WORKSPACE,
                    "--account", "operator@example.com",
                ])
            self.assertEqual(code, 0)
            profile = json.loads((Path(directory) / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(profile["execution"]["tenant_id"], TENANT)
            self.assertEqual(profile["credentials"], [])
            self.assertEqual(profile["sources"], [])
            plan = build_plan(load_profile(Path(directory) / "instance.json"))
            self.assertEqual(plan["execution"]["mode"], "delegated_assisted")
            self.assertEqual(plan["execution"]["workspace_id"], WORKSPACE)
            self.assertNotIn("account", plan["execution"])
            checklist = (Path(directory) / "CHECKLIST.md").read_text(encoding="utf-8")
            self.assertIn("session login", checklist)
            self.assertNotIn("SP OIDC", checklist)

    def test_sp_and_wrong_account_are_rejected_before_fabric_access(self):
        for user, code in (
            ({"type": "servicePrincipal", "name": "operator@example.com"}, "user_identity_required"),
            ({"type": "user", "name": "other@example.com"}, "account_mismatch"),
        ):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                session = UserSession(TENANT, WORKSPACE, "operator@example.com", Path(directory))
                response = subprocess.CompletedProcess([], 0, json.dumps({"tenantId": TENANT, "user": user}), "")
                with patch("fabric_agentic.user_session.shutil.which", return_value="az.cmd"), patch(
                    "fabric_agentic.user_session.subprocess.run", return_value=response
                ) as command:
                    with self.assertRaisesRegex(UserSessionError, code):
                        session.preflight()
                self.assertEqual(command.call_count, 1)

    def test_expired_session_never_echoes_cli_error_or_opens_login(self):
        with tempfile.TemporaryDirectory() as directory:
            session = UserSession(TENANT, WORKSPACE, "operator@example.com", Path(directory))
            response = subprocess.CompletedProcess([], 1, "private-token", "private-error")
            with patch("fabric_agentic.user_session.shutil.which", return_value="az.cmd"), patch(
                "fabric_agentic.user_session.subprocess.run", return_value=response
            ) as command:
                with self.assertRaises(UserSessionError) as failure:
                    session.preflight()
            self.assertEqual(str(failure.exception), "login_required")
            self.assertEqual(command.call_count, 1)

    def test_login_is_interactive_tenant_specific_and_needs_no_subscription(self):
        with tempfile.TemporaryDirectory() as directory:
            session = UserSession(TENANT, WORKSPACE, "operator@example.com", Path(directory))
            identity = {"tenantId": TENANT, "user": {"type": "user", "name": "OPERATOR@example.com"}}
            responses = [subprocess.CompletedProcess([], 0, None, None),
                         subprocess.CompletedProcess([], 0, json.dumps(identity), "")]
            with patch("fabric_agentic.user_session.shutil.which", return_value="az.cmd"), patch(
                "fabric_agentic.user_session.subprocess.run", side_effect=responses
            ) as command:
                session.login()
            login = command.call_args_list[0]
            self.assertIn("--allow-no-subscriptions", login.args[0])
            self.assertIn(TENANT, login.args[0])
            self.assertIsNone(login.kwargs["stdout"])
            self.assertEqual(login.kwargs["env"]["AZURE_CONFIG_DIR"], str(session.directory))

    def test_cache_is_distinct_for_tenant_workspace_and_account(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            sessions = (
                UserSession(TENANT, WORKSPACE, "operator@example.com", home),
                UserSession(WORKSPACE, WORKSPACE, "operator@example.com", home),
                UserSession(TENANT, TENANT, "operator@example.com", home),
                UserSession(TENANT, WORKSPACE, "other@example.com", home),
            )
            self.assertEqual(len({session.directory for session in sessions}), 4)
            self.assertEqual(sessions[0].directory,
                             UserSession(TENANT, WORKSPACE, "OPERATOR@example.com", home).directory)

    def test_workspace_mismatch_and_api_errors_are_sanitized(self):
        for api_error, expected in (
            (None, "workspace_mismatch"),
            (urllib.error.HTTPError("private-url", 401, "private-detail", {}, None), "login_required"),
            (urllib.error.HTTPError("private-url", 403, "private-detail", {}, None), "permission_denied"),
            (urllib.error.HTTPError("private-url", 302, "private-detail", {}, None), "fabric_request_failed"),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                session = UserSession(TENANT, WORKSPACE, "operator@example.com", Path(directory))
                identity = {"tenantId": TENANT, "user": {"type": "user", "name": "operator@example.com"}}
                responses = [subprocess.CompletedProcess([], 0, json.dumps(payload), "") for payload in (
                    identity, {"accessToken": "private-token"},
                )]
                response = MagicMock()
                response.read.return_value = json.dumps({"id": TENANT, "description": "private-data"}).encode()
                response.__enter__.return_value = response
                with patch("fabric_agentic.user_session.shutil.which", return_value="az.cmd"), patch(
                    "fabric_agentic.user_session.subprocess.run", side_effect=responses
                ), patch("fabric_agentic.user_session.urllib.request.build_opener") as opener:
                    opener.return_value.open.side_effect = api_error
                    opener.return_value.open.return_value = response
                    with self.assertRaises(UserSessionError) as failure:
                        session.preflight()
                self.assertEqual(str(failure.exception), expected)

    def test_logout_uses_only_the_selected_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            session = UserSession(TENANT, WORKSPACE, "operator@example.com", Path(directory))
            with patch("fabric_agentic.user_session.shutil.which", return_value="az.cmd"), patch(
                "fabric_agentic.user_session.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")
            ) as command:
                session.logout()
            self.assertEqual(command.call_args.args[0], ["az.cmd", "logout", "--output", "none"])
            self.assertEqual(command.call_args.kwargs["env"]["AZURE_CONFIG_DIR"], str(session.directory))

    def test_status_command_checks_the_profile_destination_without_login(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "instance.json"
            config.write_text(json.dumps({
                "schema_version": "1.0",
                "project": {"slug": "client", "display_name": "Client"},
                "tracker": {"type": "github_issues"},
                "environments": ["dev"], "sources": [], "credentials": [],
                "execution": {"mode": "delegated_assisted", "tenant_id": TENANT,
                              "workspace_id": WORKSPACE, "account": "operator@example.com"},
            }), encoding="utf-8")
            identity = {"tenantId": TENANT, "user": {"type": "user", "name": "operator@example.com"}}
            responses = [subprocess.CompletedProcess([], 0, json.dumps(payload), "") for payload in (
                identity, {"accessToken": "private-token"},
            )]
            response = MagicMock()
            response.read.return_value = json.dumps({"id": WORKSPACE}).encode()
            response.__enter__.return_value = response
            output = io.StringIO()
            with redirect_stdout(output), patch("fabric_agentic.user_session.shutil.which", return_value="az.cmd"), patch(
                "fabric_agentic.user_session.subprocess.run", side_effect=responses
            ) as command, patch("fabric_agentic.user_session.urllib.request.build_opener") as opener:
                opener.return_value.open.return_value = response
                code = main(["--home", directory, "session", "status", "--config", str(config)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["workspace_access"], "read_verified")
            self.assertNotIn("private-token", output.getvalue())
            self.assertTrue(all("login" not in call.args[0] for call in command.call_args_list))

    def test_preflight_returns_only_destination_and_read_access(self):
        with tempfile.TemporaryDirectory() as directory:
            session = UserSession(TENANT, WORKSPACE, "operator@example.com", Path(directory))
            identity = {"tenantId": TENANT, "user": {"type": "user", "name": "operator@example.com"}}
            responses = [
                subprocess.CompletedProcess([], 0, json.dumps(identity), ""),
                subprocess.CompletedProcess([], 0, json.dumps({"accessToken": "private-token"}), ""),
            ]
            response = MagicMock()
            response.read.return_value = json.dumps({"id": WORKSPACE, "description": "private data"}).encode()
            response.__enter__.return_value = response
            with patch("fabric_agentic.user_session.shutil.which", return_value="az.cmd"), patch(
                "fabric_agentic.user_session.subprocess.run", side_effect=responses
            ), patch("fabric_agentic.user_session.urllib.request.build_opener") as opener:
                opener.return_value.open.return_value = response
                report = session.preflight()
            self.assertEqual(report["workspace_access"], "read_verified")
            self.assertNotIn("private", json.dumps(report))
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE}")

    def test_wrong_tenant_stops_before_token_acquisition(self):
        with tempfile.TemporaryDirectory() as directory:
            session = UserSession(TENANT, WORKSPACE, "operator@example.com", Path(directory))
            response = subprocess.CompletedProcess([], 0, json.dumps({
                "tenantId": WORKSPACE,
                "user": {"type": "user", "name": "operator@example.com"},
            }), "secret error detail")
            with patch("fabric_agentic.user_session.shutil.which", return_value="az.cmd"), patch(
                "fabric_agentic.user_session.subprocess.run", return_value=response
            ) as command:
                with self.assertRaisesRegex(UserSessionError, "tenant_mismatch"):
                    session.check_identity()
            self.assertEqual(command.call_count, 1)
            self.assertNotIn("secret", str(session.safe_status()))


if __name__ == "__main__":
    unittest.main()