"""Deterministic local dispatcher for fresh Claude Code Dev Agent sessions.

Run as ``python -m scripts.dev_dispatcher`` so shared package imports resolve.
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

from scripts.github_app_auth import create_installation_token


ADO_SCOPE = "https://app.vssps.visualstudio.com"


class DispatcherError(Exception):
    """Raised without including credentials or response bodies."""


@dataclass(frozen=True)
class DispatcherConfig:
    organization: str
    project: str
    tenant_domain: str
    ado_app_id: str
    certificate_thumbprint: str
    github_owner: str
    github_repository: str
    github_app_id: str
    github_installation_id: str
    github_private_key_path: Path
    repository_path: Path
    claude_command: str
    poll_seconds: int


def load_config(config_path: Path) -> DispatcherConfig:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        return DispatcherConfig(
            organization=config["azure_devops"]["organization"],
            project=config["azure_devops"]["project"],
            tenant_domain=config["azure_devops"]["tenant_domain"],
            ado_app_id=config["azure_devops"]["app_id"],
            certificate_thumbprint=config["azure_devops"]["certificate_thumbprint"],
            github_owner=config["github"]["owner"],
            github_repository=config["github"]["repository"],
            github_app_id=config["github"]["app_id"],
            github_installation_id=config["github"]["installation_id"],
            github_private_key_path=Path(config["github"]["private_key_path"]),
            repository_path=Path(config["agent"]["repository_path"]),
            claude_command=config["agent"]["claude_command"],
            poll_seconds=int(config["agent"]["poll_seconds"]),
        )
    except (KeyError, OSError, ValueError, TypeError) as error:
        raise DispatcherError("dispatcher configuration is invalid") from error


def acquire_ado_token(config: DispatcherConfig) -> str:
    script = f"""
$ErrorActionPreference = 'Stop'
Connect-AzAccount -ServicePrincipal -ApplicationId '{config.ado_app_id}' -Tenant '{config.tenant_domain}' -CertificateThumbprint '{config.certificate_thumbprint}' -SkipContextPopulation -WarningAction SilentlyContinue | Out-Null
$accessToken = Get-AzAccessToken -ResourceUrl '{ADO_SCOPE}'
$token = if ($accessToken.Token -is [System.Security.SecureString]) {{
  $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($accessToken.Token)
  try {{ [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }} finally {{ [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }}
}} else {{ $accessToken.Token }}
[Console]::Out.Write($token)
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise DispatcherError("Azure DevOps token acquisition failed")
    return result.stdout.strip()


class AzureDevOpsClient:
    def __init__(self, config: DispatcherConfig, token_provider: Callable[[DispatcherConfig], str] = acquire_ado_token):
        self.config = config
        self.token_provider = token_provider

    def request(self, method: str, path: str, body: dict | None = None) -> dict:
        token = self.token_provider(self.config)
        request = Request(
            f"https://dev.azure.com/{self.config.organization}/{self.config.project}{path}",
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            method=method,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request) as response:
                return json.load(response)
        except Exception as error:
            raise DispatcherError("Azure DevOps request failed") from error

    def new_work_item_ids(self) -> list[int]:
        query = {
            "query": "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project AND [System.State] = 'To Do' AND [System.Tags] CONTAINS 'dev-agent' ORDER BY [System.ChangedDate] ASC"
        }
        result = self.request("POST", "/_apis/wit/wiql?api-version=7.1", query)
        return [int(item["id"]) for item in result.get("workItems", [])]


def load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {"dispatched_work_items": []}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DispatcherError("dispatcher state is invalid") from error


def save_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = state_path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(state_path)


def task_record(config: DispatcherConfig, work_item_id: int) -> dict:
    return {
        "work_item_id": work_item_id,
        "trigger": "new_work",
        "work_item_url": f"https://dev.azure.com/{config.organization}/{config.project}/_workitems/edit/{work_item_id}",
        "repository_path": str(config.repository_path),
        "pull_request_url": None,
    }


def refresh_clone(config: DispatcherConfig) -> None:
    token = create_installation_token(
        config.github_app_id,
        config.github_installation_id,
        config.github_private_key_path,
    ).token
    basic_auth = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    commands = [
        ["git", "-C", str(config.repository_path), "-c", f"http.extraHeader=Authorization: Basic {basic_auth}", "fetch", "origin", "main"],
        ["git", "-C", str(config.repository_path), "checkout", "main"],
        ["git", "-C", str(config.repository_path), "merge", "--ff-only", "origin/main"],
    ]
    token = None
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True, env=environment, check=False)
        if result.returncode != 0:
            raise DispatcherError("isolated repository refresh failed")


def launch_session(config: DispatcherConfig, task_path: Path) -> bool:
    prompt = (
        "You are a fresh Dev Agent session. Read the task record at "
        f"{task_path}. Then follow agents/dev/INSTRUCTIONS.md exactly. "
        "Do not access credentials, environment variables, certificate stores, or token caches."
    )
    result = subprocess.run(
        [config.claude_command, "-p", prompt, "--output-format", "json", "--permission-mode", "acceptEdits"],
        cwd=config.repository_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def run_once(config: DispatcherConfig, state_path: Path, task_directory: Path, dry_run: bool) -> list[dict]:
    client = AzureDevOpsClient(config)
    state = load_state(state_path)
    dispatched = set(state.get("dispatched_work_items", []))
    tasks = [task_record(config, work_item_id) for work_item_id in client.new_work_item_ids() if work_item_id not in dispatched]
    if not tasks or dry_run:
        return tasks

    task = tasks[0]
    refresh_clone(config)
    task_directory.mkdir(parents=True, exist_ok=True)
    task_path = task_directory / f"{uuid.uuid4()}.json"
    task_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    state["dispatched_work_items"] = [*dispatched, task["work_item_id"]]
    save_state(state_path, state)
    launch_session(config, task_path)
    return [task]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        if not args.once:
            raise DispatcherError("only --once is supported until trigger B and C are added")
        tasks = run_once(config, args.state, args.tasks, args.dry_run)
        if args.dry_run:
            print(json.dumps({"tasks": tasks}))
    except DispatcherError as error:
        print(json.dumps({"error": str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())