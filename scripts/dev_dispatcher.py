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
import socketserver
import tempfile
import shutil
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterator
from urllib.parse import quote
from urllib.request import Request, urlopen

from scripts.github_app_auth import create_installation_token
from scripts.tracker import AzureDevOpsTracker, GitHubIssuesTracker, WorkItemTracker


class DispatcherError(Exception):
    """Raised without including credentials or response bodies."""


class CredentialBrokerHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            request = json.loads(self.rfile.readline().decode("utf-8"))
            if request.get("kind") not in {"git", "gh"}:
                raise ValueError
            self.wfile.write(json.dumps({"token": self.server.token}).encode("utf-8"))
        except (AttributeError, json.JSONDecodeError, ValueError):
            self.wfile.write(b'{"error":"invalid credential request"}')


class CredentialBroker(socketserver.ThreadingTCPServer):
    allow_reuse_address = False

    def __init__(self, token: str):
        super().__init__(("127.0.0.1", 0), CredentialBrokerHandler)
        self.token = token


@contextmanager
def credential_broker_environment(token: str) -> Iterator[dict[str, str]]:
    broker = CredentialBroker(token)
    broker_thread = threading.Thread(target=broker.serve_forever, daemon=True)
    broker_thread.start()
    with tempfile.TemporaryDirectory(prefix="fabric-agentic-credentials-") as directory:
        helper = Path(directory) / "credential-helper.cmd"
        helper.write_text(
            f'@echo off\n"{sys.executable}" "{Path(__file__).with_name("dev_agent_credential_helper.py")}" git %*\n',
            encoding="utf-8",
        )
        real_gh = shutil.which("gh") or "gh"
        gh_wrapper = Path(directory) / "gh.cmd"
        gh_wrapper.write_text(
            f'@echo off\n"{sys.executable}" "{Path(__file__).with_name("dev_agent_credential_helper.py")}" gh "{real_gh}" %*\n',
            encoding="utf-8",
        )
        environment = os.environ.copy()
        environment.pop("GH_TOKEN", None)
        environment.pop("GITHUB_TOKEN", None)
        environment["GIT_ASKPASS"] = str(helper)
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["FABRIC_AGENT_CREDENTIAL_BROKER"] = f"127.0.0.1:{broker.server_address[1]}"
        environment["PATH"] = f"{directory}{os.pathsep}{environment.get('PATH', '')}"
        try:
            yield environment
        finally:
            broker.shutdown()
            broker.server_close()
            broker_thread.join(timeout=2)


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
    github_app_id: int
    github_installation_id: int
    github_private_key_path: Path
    repository_path: Path
    claude_command: str
    poll_seconds: int
    tracker_type: str = "azure_devops"  # "azure_devops" or "github_issues"


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
            github_app_id=int(config["github"]["app_id"]),
            github_installation_id=int(config["github"]["installation_id"]),
            github_private_key_path=Path(config["github"]["private_key_path"]),
            repository_path=Path(config["agent"]["repository_path"]),
            claude_command=config["agent"]["claude_command"],
            poll_seconds=int(config["agent"]["poll_seconds"]),
            tracker_type=config.get("dispatcher", {}).get("tracker_type", "azure_devops"),
        )
    except (KeyError, OSError, ValueError, TypeError) as error:
        raise DispatcherError("dispatcher configuration is invalid") from error


def create_tracker(config: DispatcherConfig, ado_token_provider: Callable[[], str]) -> WorkItemTracker:
    """Factory to create the configured work-item tracker."""
    if config.tracker_type == "github_issues":
        return GitHubIssuesTracker(
            owner=config.github_owner,
            repository=config.github_repository,
            github_app_id=config.github_app_id,
            github_installation_id=config.github_installation_id,
            github_private_key_path=config.github_private_key_path,
            agent_identity=config.dev_agent_display_name,
        )
    elif config.tracker_type == "azure_devops":
        return AzureDevOpsTracker(
            organization=config.organization,
            project=config.project,
            token_provider=ado_token_provider,
            dev_agent_display_name=config.dev_agent_display_name,
        )
    else:
        raise DispatcherError(f"Unknown tracker type: {config.tracker_type}")


def acquire_ado_token(config: DispatcherConfig) -> str:
    """Acquire Azure DevOps token via service principal certificate."""
    ADO_SCOPE = "https://app.vssps.visualstudio.com"
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


def load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {"dispatched_work_items": [], "seen_comment_ids": [], "seen_review_thread_ids": []}
    try:
        return json.loads(state_path.read_text(encoding="utf-8-sig"))
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


def stage_work_item_context(config: DispatcherConfig, tracker: WorkItemTracker, work_item_id: int | str, task_directory: Path) -> Path | None:
    context = tracker.context(work_item_id)
    repository_attachments = config.repository_path / "attachments" / str(work_item_id)
    local_attachments = sorted(path for path in repository_attachments.iterdir() if path.is_file()) if repository_attachments.is_dir() else []
    if not context.get("body") and not context.get("attachments") and not local_attachments:
        return None
    context_directory = task_directory / f"work-item-{work_item_id}"
    context_directory.mkdir(parents=True, exist_ok=True)
    context_path = context_directory / "issue-context.md"
    lines = [f"# {context.get('title', '')}", "", str(context.get("body", "")), ""]
    for index, attachment_path in enumerate(local_attachments, start=1):
        if attachment_path.stat().st_size > MAX_ATTACHMENT_BYTES:
            raise DispatcherError("work-item attachment is too large")
        lines.extend([f"## Attachment {index}", str(attachment_path), ""])
    remote_attachments = [] if local_attachments else context.get("attachments", [])
    for index, attachment_url in enumerate(remote_attachments, start=len(local_attachments) + 1):
        attachment_path = context_directory / f"attachment-{index}"
        try:
            with urlopen(attachment_url) as response:
                content = response.read(MAX_ATTACHMENT_BYTES + 1)
            if len(content) > MAX_ATTACHMENT_BYTES:
                raise DispatcherError("work-item attachment is too large")
            attachment_path.write_bytes(content)
        except Exception as error:
            raise DispatcherError("work-item attachment download failed") from error
        lines.extend([f"## Attachment {index}", str(attachment_path), ""])
    context_path.write_text("\n".join(lines), encoding="utf-8")
    return context_path


def task_record(config: DispatcherConfig, tracker: WorkItemTracker, work_item_id: int | str, trigger: str = "new_work", pull_request_url: str | None = None, context_path: Path | None = None) -> dict:
    record = {
        "work_item_id": work_item_id,
        "trigger": trigger,
        "work_item_url": tracker.item_url(work_item_id),
        "repository_path": str(config.repository_path),
        "pull_request_url": pull_request_url,
    }
    if context_path is not None:
        record["issue_context_path"] = str(context_path)
    return record


def human_reply_tasks(config: DispatcherConfig, tracker: WorkItemTracker, seen_comment_ids: set[int | str]) -> tuple[list[dict], set[int | str]]:
    tasks = []
    observed = set(seen_comment_ids)
    for work_item_id in tracker.waiting_input_items():
        for comment in tracker.comments(work_item_id):
            if comment.is_agent_comment or comment.id in observed:
                continue
            observed.add(comment.id)
            tasks.append(task_record(config, tracker, work_item_id, trigger="human_reply"))
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


def review_thread_tasks(config: DispatcherConfig, tracker: WorkItemTracker, payload: dict, seen_thread_ids: set[str]) -> tuple[list[dict], set[str]]:
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
            work_item_id = int(match.group(1))
            tasks.append(task_record(config, tracker, work_item_id, trigger="review_thread", pull_request_url=pull_request["url"]))
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


@dataclass(frozen=True)
class SessionOutcome:
    returncode: int
    is_error: bool
    session_id: str | None
    num_turns: int | None
    changed_repository: bool

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.is_error

    @property
    def outcome(self) -> str:
        if not self.succeeded:
            return "failed"
        return "productive" if self.changed_repository else "no_work"


DEV_AGENT_ALLOWED_TOOLS = (
    "Read",
    "Edit",
    "Write",
    "Bash(git status *)",
    "Bash(git diff *)",
    "Bash(git switch --create feature/*)",
    "Bash(git add *)",
    "Bash(git commit *)",
    "Bash(git push origin HEAD:refs/heads/feature/*)",
    "Bash(gh pr create *)",
    "Bash(python -m pytest *)",
)


def build_session_command(config: DispatcherConfig, task_path: Path) -> list[str]:
    prompt = (
        "You are a fresh Dev Agent session. Read the task record at "
        f"{task_path}, then read the referenced issue context and attachments. "
        "Implement the requested work described there, run the required tests, update the "
        "affected documentation, and prepare the feature branch and pull request as instructed. "
        "Then follow agents/dev/INSTRUCTIONS.md exactly. "
        "Do not access credentials, environment variables, certificate stores, or token caches."
    )
    return [
        config.claude_command,
        "-p",
        prompt,
        "--add-dir",
        str(task_path.parent),
        "--output-format",
        "json",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        *DEV_AGENT_ALLOWED_TOOLS,
    ]


def repository_changed(config: DispatcherConfig) -> bool:
    """Report whether the session left work behind, as uncommitted files or a feature branch."""
    status = subprocess.run(
        ["git", "-C", str(config.repository_path), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0:
        return False
    if status.stdout.strip():
        return True
    branch = subprocess.run(
        ["git", "-C", str(config.repository_path), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return branch.returncode == 0 and branch.stdout.strip() not in ("", "main")


def launch_session(config: DispatcherConfig, task_path: Path) -> SessionOutcome:
    token = create_installation_token(
        config.github_app_id,
        config.github_installation_id,
        config.github_private_key_path,
    ).token
    with credential_broker_environment(token) as environment:
        result = subprocess.run(
            build_session_command(config, task_path),
            cwd=config.repository_path,
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )
    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return SessionOutcome(
        returncode=result.returncode,
        is_error=bool(payload.get("is_error", False)),
        session_id=payload.get("session_id"),
        num_turns=payload.get("num_turns"),
        changed_repository=repository_changed(config),
    )


SMOKE_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["documents_read"],
    "properties": {"documents_read": {"type": "array", "items": {"type": "string"}, "minItems": 1}},
}

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


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


def run_smoke(config: DispatcherConfig, work_item_id: int | str, task_directory: Path) -> list[str]:
    """Run smoke test on a single work item: Doing → (smoke) → Done."""
    ado_token_provider = lambda: acquire_ado_token(config)
    tracker = create_tracker(config, ado_token_provider)
    tracker.set_state(work_item_id, "Doing")
    refresh_clone(config)
    task_directory.mkdir(parents=True, exist_ok=True)
    task_path = task_directory / f"smoke-{uuid.uuid4()}.json"
    task_path.write_text(json.dumps(task_record(config, tracker, work_item_id), indent=2) + "\n", encoding="utf-8")
    documents = launch_smoke_session(config, task_path)
    tracker.add_comment(work_item_id, smoke_comment(documents))
    tracker.set_state(work_item_id, "Done")
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


def run_once(config: DispatcherConfig, state_path: Path, task_directory: Path, dry_run: bool, log_path: Path | None = None) -> list[dict]:
    ado_token_provider = lambda: acquire_ado_token(config)
    tracker = create_tracker(config, ado_token_provider)
    state = load_state(state_path)
    dispatched = set(state.get("dispatched_work_items", []))
    new_work = [task_record(config, tracker, work_item_id) for work_item_id in tracker.new_items() if work_item_id not in dispatched]
    human_replies, seen_comments = human_reply_tasks(config, tracker, set(state.get("seen_comment_ids", [])))
    review_payload = github_graphql(config, REVIEW_THREADS_QUERY, {"owner": config.github_owner, "repository": config.github_repository})
    review_threads, seen_threads = review_thread_tasks(config, tracker, review_payload, set(state.get("seen_review_thread_ids", [])))
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
    context_path = stage_work_item_context(config, tracker, task["work_item_id"], task_directory)
    task = task_record(config, tracker, task["work_item_id"], trigger=task["trigger"], pull_request_url=task.get("pull_request_url"), context_path=context_path)
    task_path = task_directory / f"{uuid.uuid4()}.json"
    task_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    state["dispatched_work_items"] = [*dispatched, task["work_item_id"]]
    state["seen_comment_ids"] = sorted(seen_comments)
    state["seen_review_thread_ids"] = sorted(seen_threads)
    save_state(state_path, state)
    outcome = launch_session(config, task_path)
    if log_path is not None:
        log_event(
            log_path,
            "session_completed",
            work_item_id=task["work_item_id"],
            returncode=outcome.returncode,
            is_error=outcome.is_error,
            session_id=outcome.session_id,
            num_turns=outcome.num_turns,
            changed_repository=outcome.changed_repository,
            outcome=outcome.outcome,
        )
    if not outcome.succeeded:
        raise DispatcherError("Dev Agent session failed")
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
            tasks = run_once(config, state_path, task_directory, dry_run=False, log_path=log_path)
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
            tasks = run_once(config, args.state, args.tasks, args.dry_run, log_path=args.log)
            log_event(args.log, "dry_run_completed" if args.dry_run else "once_completed", task_count=len(tasks), work_item_ids=[task["work_item_id"] for task in tasks], triggers=[task["trigger"] for task in tasks])
            if args.dry_run:
                print(json.dumps({"tasks": tasks}))
    except DispatcherError as error:
        print(json.dumps({"error": str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())