"""Privately acquire tracker credentials from explicitly selected user CLI contexts."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen


class TrackerAuthError(Exception):
    """Public authentication failure code without credential or API response material."""


def _run_cli(name: str, arguments: list[str], directory: Path) -> str:
    if os.environ.get("FABRIC_AGENT_CREDENTIAL_BROKER"):
        raise TrackerAuthError("tracker_login_requires_operator_context")
    executable = shutil.which(name)
    if executable is None:
        raise TrackerAuthError("tracker_cli_missing")
    environment = dict(os.environ)
    for key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN"):
        environment.pop(key, None)
    environment["GH_CONFIG_DIR" if name == "gh" else "AZURE_CONFIG_DIR"] = str(directory)
    environment["GH_HOST"] = "github.com"
    environment["GH_PROMPT_DISABLED"] = "1"
    try:
        result = subprocess.run(
            [executable, *arguments], env=environment, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise TrackerAuthError("tracker_authentication_failed") from error
    if result.returncode or not result.stdout.strip():
        raise TrackerAuthError("tracker_login_required")
    return result.stdout.strip()


def github_user_credentials(account: str, directory: Path) -> tuple[str, str]:
    token = _run_cli("gh", ["auth", "token", "--hostname", "github.com"], directory)
    if "\n" in token or "\r" in token:
        raise TrackerAuthError("tracker_invalid_token_response")
    request = Request("https://api.github.com/user", headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
    })
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (OSError, ValueError) as error:
        raise TrackerAuthError("tracker_identity_verification_failed") from error
    login = payload.get("login") if isinstance(payload, dict) else None
    if not isinstance(login, str) or login.casefold() != account.casefold():
        raise TrackerAuthError("tracker_account_mismatch")
    if payload.get("type") == "Bot":
        raise TrackerAuthError("tracker_user_identity_required")
    return token, login


def azure_user_token(account: str, tenant_id: str, directory: Path) -> str:
    try:
        context = json.loads(_run_cli("az", ["account", "show", "--output", "json"], directory))
        if not isinstance(context, dict) or str(context.get("tenantId", "")).casefold() != tenant_id.casefold():
            raise TrackerAuthError("tracker_tenant_mismatch")
        user = context.get("user")
        if not isinstance(user, dict) or user.get("type") != "user":
            raise TrackerAuthError("tracker_user_identity_required")
        if str(user.get("name", "")).casefold() != account.casefold():
            raise TrackerAuthError("tracker_account_mismatch")
        payload = json.loads(_run_cli("az", [
            "account", "get-access-token", "--tenant", tenant_id,
            "--resource", "https://app.vssps.visualstudio.com", "--output", "json",
        ], directory))
    except (ValueError, TypeError) as error:
        raise TrackerAuthError("tracker_invalid_identity_response") from error
    token = payload.get("accessToken") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not token or "\n" in token or "\r" in token:
        raise TrackerAuthError("tracker_invalid_token_response")
    return token