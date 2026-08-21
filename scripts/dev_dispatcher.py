"""Deterministic local dispatcher for fresh Claude Code Dev Agent sessions.

Run as ``python -m scripts.dev_dispatcher`` so shared package imports resolve.
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
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
    dev_agent_display_name: str
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
            dev_agent_display_name=config["azure_devops"]["dev_agent_display_name"],
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

    def request(self, method: str, path: str, body: dict | list | None = None) -> dict:
        token = self.token_provider(self.config)
        content_type = "application/json-patch+json" if isinstance(body, list) else "application/json"
        request = Request(
            f"https://dev.azure.com/{self.config.organization}/{self.config.project}{path}",
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            method=method,
            headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
        )
        try:
            with urlopen(request) as response:
                return json.load(response)
        except Exception as error:
            raise DispatcherError("Azure DevOps request failed") from error

    def new_work_item_ids(self) -> list[int]:
        return self.work_item_ids("To Do", "[System.Tags] CONTAINS 'dev-agent'")

    def waiting_input_work_item_ids(self) -> list[int]:
        return self.work_item_ids("Doing", "[System.Tags] CONTAINS 'dev-agent' AND [System.Tags] CONTAINS 'waiting-input'")

    def work_item_ids(self, state: str, tags_filter: str) -> list[int]:
        query = {
            "query": f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project AND [System.State] = '{state}' AND {tags_filter} ORDER BY [System.ChangedDate] ASC"
        }
        result = self.request("POST", "/_apis/wit/wiql?api-version=7.1", query)
        return [int(item["id"]) for item in result.get("workItems", [])]

    def comments(self, work_item_id: int) -> list[dict]:
        result = self.request("GET", f"/_apis/wit/workItems/{work_item_id}/comments?order=asc&api-version=7.1-preview.4")
        return result.get("comments", [])

    def add_comment(self, work_item_id: int, text: str) -> None:
        self.request("POST", f"/_apis/wit/workItems/{work_item_id}/comments?api-version=7.1-preview.4", {"text": text})

    def set_state(self, work_item_id: int, state: str) -> None:
        self.request("PATCH", f"/_apis/wit/workitems/{work_item_id}?api-version=7.1", [{"op": "add", "path": "/fields/System.State", "value": state}])


def load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {"dispatched_work_items": [], "seen_comment_ids": [], "seen_review_thread_ids": []}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DispatcherError("dispatcher state is invalid") from error


def save_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = state_path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(state_path)


def log_event(log_path: Path, event: str, **fields: object) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": datetime.now(UTC).isoformat(), "event": event, **fields}
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(payload) + "\n")


def task_record(config: DispatcherConfig, work_item_id: int, trigger: str = "new_work", pull_request_url: str | None = None) -> dict:
    return {
        "work_item_id": work_item_id,
        "trigger": trigger,
        "work_item_url": f"https://dev.azure.com/{config.organization}/{config.project}/_workitems/edit/{work_item_id}",
        "repository_path": str(config.repository_path),
        "pull_request_url": pull_request_url,
    }


def human_reply_tasks(config: DispatcherConfig, client: AzureDevOpsClient, seen_comment_ids: set[int]) -> tuple[list[dict], set[int]]:
    tasks = []
    observed = set(seen_comment_ids)
    for work_item_id in client.waiting_input_work_item_ids():
        for comment in client.comments(work_item_id):
            comment_id = int(comment["commentId"])
            author = comment.get("createdBy", {}).get("displayName", "")
            if comment_id in observed or author == config.dev_agent_display_name:
                continue
            observed.add(comment_id)
            tasks.append(task_record(config, work_item_id, trigger="human_reply"))
    return tasks, observed


def github_graphql(config: DispatcherConfig, query: str, variables: dict) -> dict:
    token = create_installation_token(config.github_app_id, config.github_installation_id, config.github_private_key_path).token
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"},
    )
    try:
        with urlopen(request) as response:
            result = json.load(response)
    except Exception as error:
        raise DispatcherError("GitHub review-thread request failed") from error
    if result.get("errors"):
        raise DispatcherError("GitHub review-thread request failed")
    return result["data"]


def review_thread_tasks(config: DispatcherConfig, payload: dict, seen_thread_ids: set[str]) -> tuple[list[dict], set[str]]:
    tasks = []
    observed = set(seen_thread_ids)
    for pull_request in payload.get("repository", {}).get("pullRequests", {}).get("nodes", []):
        match = re.fullmatch(r"feature/wi-(\d+)-.+", pull_request.get("headRefName", ""))
        if not match:
            continue
        for thread in pull_request.get("reviewThreads", {}).get("nodes", []):
            thread_id = thread["id"]
            if thread["isResolved"] or thread_id in observed:
                continue
            observed.add(thread_id)
            tasks.append(task_record(config, int(match.group(1)), trigger="review_thread", pull_request_url=pull_request["url"]))
    return tasks, observed


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


SMOKE_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["documents_read"],
    "properties": {"documents_read": {"type": "array", "items": {"type": "string"}, "minItems": 1}},
}


def launch_smoke_session(config: DispatcherConfig, task_path: Path) -> list[str]:
    prompt = (
        "This is the S0-14 smoke test. Read the task record at "
        f"{task_path}, then read CONTEXT.md, AGENTS.md, "
        "docs/functional/01-ciclo-di-vita-ticket.md, and "
        "docs/functional/02-come-scrivere-un-ticket.md. Do not edit files, use Git, "
        "access credentials, environment variables, certificate stores, tokens, or Fabric. "
        "Return only the structured list of documents you actually read."
    )
    result = subprocess.run(
        [
            config.claude_command,
            "-p",
            prompt,
            "--allowedTools",
            "Read",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(SMOKE_OUTPUT_SCHEMA),
        ],
        cwd=config.repository_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise DispatcherError("smoke Claude session failed")
    try:
        documents = json.loads(result.stdout)["structured_output"]["documents_read"]
    except (KeyError, TypeError, ValueError) as error:
        raise DispatcherError("smoke Claude session returned invalid output") from error
    if not all(isinstance(document, str) for document in documents):
        raise DispatcherError("smoke Claude session returned invalid output")
    return documents


def smoke_comment(documents_read: list[str]) -> str:
    documents = "\n".join(f"- {document}" for document in documents_read)
    return f"[fabric-agentic-dev-agent]\nS0-14 smoke test completed.\n\nDOCUMENTI LETTI\n{documents}"


def run_smoke(config: DispatcherConfig, work_item_id: int, task_directory: Path) -> list[str]:
    client = AzureDevOpsClient(config)
    client.set_state(work_item_id, "Doing")
    refresh_clone(config)
    task_directory.mkdir(parents=True, exist_ok=True)
    task_path = task_directory / f"smoke-{uuid.uuid4()}.json"
    task_path.write_text(json.dumps(task_record(config, work_item_id), indent=2) + "\n", encoding="utf-8")
    documents = launch_smoke_session(config, task_path)
    client.add_comment(work_item_id, smoke_comment(documents))
    client.set_state(work_item_id, "Done")
    return documents


REVIEW_THREADS_QUERY = """
query($owner: String!, $repository: String!) {
    repository(owner: $owner, name: $repository) {
        pullRequests(states: OPEN, first: 100) {
            nodes {
                url
                headRefName
                reviewThreads(first: 100) { nodes { id isResolved } }
            }
        }
    }
}
"""


def run_once(config: DispatcherConfig, state_path: Path, task_directory: Path, dry_run: bool) -> list[dict]:
    client = AzureDevOpsClient(config)
    state = load_state(state_path)
    dispatched = set(state.get("dispatched_work_items", []))
    new_work = [task_record(config, work_item_id) for work_item_id in client.new_work_item_ids() if work_item_id not in dispatched]
    human_replies, seen_comments = human_reply_tasks(config, client, set(state.get("seen_comment_ids", [])))
    review_payload = github_graphql(config, REVIEW_THREADS_QUERY, {"owner": config.github_owner, "repository": config.github_repository})
    review_threads, seen_threads = review_thread_tasks(config, review_payload, set(state.get("seen_review_thread_ids", [])))
    tasks = [*new_work, *human_replies, *review_threads]
    if not tasks or dry_run:
        if not dry_run:
            state["seen_comment_ids"] = sorted(seen_comments)
            state["seen_review_thread_ids"] = sorted(seen_threads)
            save_state(state_path, state)
        return tasks

    task = tasks[0]
    refresh_clone(config)
    task_directory.mkdir(parents=True, exist_ok=True)
    task_path = task_directory / f"{uuid.uuid4()}.json"
    task_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    state["dispatched_work_items"] = [*dispatched, task["work_item_id"]]
    state["seen_comment_ids"] = sorted(seen_comments)
    state["seen_review_thread_ids"] = sorted(seen_threads)
    save_state(state_path, state)
    launch_session(config, task_path)
    return [task]


def run_polling(
    config: DispatcherConfig,
    state_path: Path,
    task_directory: Path,
    log_path: Path,
    cycles: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    completed_cycles = 0
    while cycles is None or completed_cycles < cycles:
        started_at = time.monotonic()
        try:
            tasks = run_once(config, state_path, task_directory, dry_run=False)
            log_event(
                log_path,
                "poll_completed",
                task_count=len(tasks),
                work_item_ids=[task["work_item_id"] for task in tasks],
                triggers=[task["trigger"] for task in tasks],
                duration_ms=round((time.monotonic() - started_at) * 1000),
            )
        except DispatcherError as error:
            log_event(log_path, "poll_failed", reason=str(error))
        completed_cycles += 1
        if cycles is None or completed_cycles < cycles:
            sleep(config.poll_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll", action="store_true")
    parser.add_argument("--smoke-work-item-id", type=int)
    parser.add_argument("--cycles", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        selected_modes = sum([args.once, args.poll, args.smoke_work_item_id is not None])
        if selected_modes != 1:
            raise DispatcherError("choose exactly one execution mode")
        if args.poll and args.dry_run:
            raise DispatcherError("--poll cannot be combined with --dry-run")
        if args.smoke_work_item_id is not None and args.dry_run:
            raise DispatcherError("smoke mode cannot be combined with --dry-run")
        if args.poll:
            run_polling(config, args.state, args.tasks, args.log, args.cycles)
        elif args.smoke_work_item_id is not None:
            documents = run_smoke(config, args.smoke_work_item_id, args.tasks)
            log_event(args.log, "smoke_completed", work_item_id=args.smoke_work_item_id, documents_read=documents)
        else:
            tasks = run_once(config, args.state, args.tasks, args.dry_run)
            log_event(args.log, "dry_run_completed" if args.dry_run else "once_completed", task_count=len(tasks), work_item_ids=[task["work_item_id"] for task in tasks], triggers=[task["trigger"] for task in tasks])
            if args.dry_run:
                print(json.dumps({"tasks": tasks}))
    except DispatcherError as error:
        print(json.dumps({"error": str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())