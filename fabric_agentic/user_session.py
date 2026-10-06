"""Operator-assisted Fabric access with a client-specific Azure CLI context."""

import hashlib
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
import uuid
from pathlib import Path


class UserSessionError(Exception):
    """A public failure code, never raw authentication output."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UserSession:
    def __init__(self, tenant_id: str, workspace_id: str, account: str, home: Path):
        try:
            self.tenant_id = str(uuid.UUID(tenant_id))
            self.workspace_id = str(uuid.UUID(workspace_id))
        except (ValueError, AttributeError) as error:
            raise UserSessionError("invalid_destination") from error
        if not isinstance(account, str) or not account.strip() or account.startswith("-"):
            raise UserSessionError("invalid_account")
        self.account = account.strip()
        account_key = hashlib.sha256(self.account.casefold().encode("utf-8")).hexdigest()
        self.directory = home / "user-sessions" / self.tenant_id / self.workspace_id / account_key

    def safe_status(self) -> dict:
        return {
            "mode": "delegated_assisted",
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
        }

    def _command(self, arguments: list[str], interactive: bool = False) -> str:
        executable = shutil.which("az")
        if executable is None:
            raise UserSessionError("azure_cli_missing")
        self.directory.mkdir(parents=True, exist_ok=True)
        environment = dict(os.environ)
        environment["AZURE_CONFIG_DIR"] = str(self.directory)
        try:
            result = subprocess.run(
                [executable, *arguments],
                env=environment,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=None if interactive else subprocess.PIPE,
                stderr=None if interactive else subprocess.PIPE,
                check=False,
                timeout=None if interactive else 60,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise UserSessionError("authentication_command_failed") from error
        if result.returncode:
            raise UserSessionError("login_required")
        return result.stdout or ""

    def check_identity(self) -> dict:
        try:
            context = json.loads(self._command(["account", "show", "--output", "json"]))
        except (ValueError, TypeError) as error:
            raise UserSessionError("invalid_identity_response") from error
        if not isinstance(context, dict):
            raise UserSessionError("invalid_identity_response")
        if str(context.get("tenantId", "")).lower() != self.tenant_id:
            raise UserSessionError("tenant_mismatch")
        user = context.get("user")
        if not isinstance(user, dict) or user.get("type") != "user":
            raise UserSessionError("user_identity_required")
        if str(user.get("name", "")).casefold() != self.account.casefold():
            raise UserSessionError("account_mismatch")
        return self.safe_status()

    def login(self) -> dict:
        self._command([
            "login", "--tenant", self.tenant_id,
            "--allow-no-subscriptions", "--output", "none",
        ], interactive=True)
        return self.check_identity()

    def logout(self) -> dict:
        self._command(["logout", "--output", "none"])
        return self.safe_status()

    def preflight(self) -> dict:
        report = self.check_identity()
        try:
            token_response = json.loads(self._command([
                "account", "get-access-token", "--tenant", self.tenant_id,
                "--resource", "https://api.fabric.microsoft.com", "--output", "json",
            ]))
            token = token_response.get("accessToken") if isinstance(token_response, dict) else None
            if not isinstance(token, str) or not token or "\n" in token or "\r" in token:
                raise UserSessionError("invalid_token_response")
        except (ValueError, TypeError) as error:
            raise UserSessionError("invalid_token_response") from error
        request = urllib.request.Request(
            f"https://api.fabric.microsoft.com/v1/workspaces/{self.workspace_id}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            method="GET",
        )
        try:
            opener = urllib.request.build_opener(_NoRedirect())
            with opener.open(request, timeout=30) as response:
                workspace = json.loads(response.read())
        except urllib.error.HTTPError as error:
            codes = {401: "login_required", 403: "permission_denied", 404: "workspace_unavailable", 429: "throttled"}
            raise UserSessionError(codes.get(error.code, "fabric_request_failed")) from error
        except (OSError, ValueError) as error:
            raise UserSessionError("fabric_request_failed") from error
        if not isinstance(workspace, dict) or str(workspace.get("id", "")).lower() != self.workspace_id:
            raise UserSessionError("workspace_mismatch")
        report["workspace_access"] = "read_verified"
        return report