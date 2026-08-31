"""Deterministic dispatcher for fresh Issue Agent sessions."""

import argparse
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fabric_agentic.agent_session import session_failure_reason
from fabric_agentic.config_paths import expand_path, read_json_config
from fabric_agentic.polling import PollingStopped, run_polling
from fabric_agentic.credential_broker import credential_broker_environment
from fabric_agentic.github_app_auth import GITHUB_API, create_installation_token
from scripts.issue_package_publish import IDENTITY_MARKER, app_bot_login


PUBLISHER_MODULE = "scripts.issue_package_publish"
INTAKE_LABEL = "issue-agent"
APPROVED_LABEL = "dev-agent"


class IssueDispatcherError(Exception):
    """Raised without including credentials or response bodies."""


@dataclass(frozen=True)
class IssueDispatcherConfig:
    github_owner: str
    github_repository: str
    github_app_id: int
    github_installation_id: int
    github_private_key_path: Path
    repository_path: Path
    claude_command: str
    poll_seconds: int = 30


@dataclass(frozen=True)
class IntakeCandidate:
    number: int
    title: str
    body: str
    url: str


def load_config(config_path: Path) -> IssueDispatcherConfig:
    try:
        config = read_json_config(config_path)
        github = config["github"]
        agent = config["agent"]
        app_id = int(github["app_id"])
        installation_id = int(github["installation_id"])
        return IssueDispatcherConfig(
            github_owner=github["owner"],
            github_repository=github["repository"],
            github_app_id=app_id,
            github_installation_id=installation_id,
            github_private_key_path=expand_path(github["private_key_path"]),
            repository_path=expand_path(agent["repository_path"]),
            claude_command=agent["claude_command"],
            poll_seconds=int(agent.get("poll_seconds", 30)),
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise IssueDispatcherError("issue dispatcher configuration is invalid") from error


def github_request(method: str, path: str, token: str) -> object:
    request = Request(
        f"{GITHUB_API}{path}",
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request) as response:
            return json.load(response)
    except (OSError, HTTPError) as error:
        raise IssueDispatcherError(f"GitHub intake discovery failed: {method} {path}") from error


def open_intake_issues(config: IssueDispatcherConfig, token: str) -> list[dict]:
    payload = github_request(
        "GET",
        f"/repos/{config.github_owner}/{config.github_repository}/issues"
        f"?state=open&labels={INTAKE_LABEL}&per_page=100",
        token,
    )
    return [issue for issue in payload if "pull_request" not in issue] if isinstance(payload, list) else []


def issue_comments(config: IssueDispatcherConfig, issue: int, token: str) -> list[dict]:
    payload = github_request(
        "GET",
        f"/repos/{config.github_owner}/{config.github_repository}/issues/{issue}/comments?per_page=100",
        token,
    )
    return payload if isinstance(payload, list) else []


def intake_candidates(config: IssueDispatcherConfig, token: str, issue_login: str) -> list[IntakeCandidate]:
    candidates = []
    for issue in open_intake_issues(config, token):
        number = issue.get("number")
        labels = {label.get("name") for label in issue.get("labels", [])}
        if not isinstance(number, int) or APPROVED_LABEL in labels:
            continue
        published = any(
            (comment.get("user") or {}).get("login") == issue_login
            and IDENTITY_MARKER in (comment.get("body") or "")
            for comment in issue_comments(config, number, token)
        )
        if published:
            continue
        candidates.append(
            IntakeCandidate(
                number=number,
                title=str(issue.get("title", "")),
                body=str(issue.get("body") or ""),
                url=str(issue.get("html_url", "")),
            )
        )
    return candidates


@contextmanager
def session_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise IssueDispatcherError("an Issue Agent session is already active") from error
    try:
        os.close(descriptor)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def task_record(config: IssueDispatcherConfig, candidate: IntakeCandidate) -> dict:
    return {
        "issue": candidate.number,
        "title": candidate.title,
        "body": candidate.body,
        "issue_url": candidate.url,
        "repository_path": str(config.repository_path),
        "trigger": "intake_issue",
    }


def load_state(state_path: Path) -> dict[str, list[int]]:
    if not state_path.exists():
        return {"dispatched_intakes": []}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
        dispatched = state.get("dispatched_intakes", [])
        if not isinstance(dispatched, list):
            raise ValueError
        return {"dispatched_intakes": dispatched}
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise IssueDispatcherError("issue dispatcher state is invalid") from error


def save_state(state_path: Path, state: dict[str, list[int]]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = state_path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(state_path)


def run_git(config: IssueDispatcherConfig, arguments: list[str], environment: dict[str, str]) -> None:
    result = subprocess.run(
        ["git", "-C", str(config.repository_path), *arguments],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    if result.returncode != 0:
        raise IssueDispatcherError(f"the issue clone cannot answer 'git {arguments[0]}'")


def prepare_issue_clone(config: IssueDispatcherConfig) -> None:
    token = create_installation_token(
        config.github_app_id,
        config.github_installation_id,
        config.github_private_key_path,
    ).token
    with credential_broker_environment(token) as environment:
        run_git(config, ["fetch", "--prune", "origin", "main"], environment)
        run_git(config, ["checkout", "main"], environment)
        run_git(config, ["merge", "--ff-only", "origin/main"], environment)


def discover_once(config: IssueDispatcherConfig) -> list[dict]:
    if config.github_app_id <= 0 or config.github_installation_id <= 0:
        raise IssueDispatcherError("the Issue Agent identity is not provisioned")
    token = create_installation_token(
        config.github_app_id,
        config.github_installation_id,
        config.github_private_key_path,
    ).token
    login = app_bot_login(str(config.github_app_id), config.github_private_key_path)
    return [task_record(config, candidate) for candidate in intake_candidates(config, token, login)]


def publisher_command(config: IssueDispatcherConfig, task: dict, package_path: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        PUBLISHER_MODULE,
        "--package-path", str(package_path),
        "--owner", config.github_owner,
        "--repository", config.github_repository,
        "--issue", str(task["issue"]),
        "--app-id", str(config.github_app_id),
        "--installation-id", str(config.github_installation_id),
        "--key-path", str(config.github_private_key_path),
    ]


def launch_issue_session(config: IssueDispatcherConfig, task_path: Path) -> str:
    prompt = (
        "You are a fresh Issue Agent session. Read the task record at "
        f"{task_path}, then follow agents/issue/INSTRUCTIONS.md exactly. "
        "Delegate requirements to karl and architecture to ralph, then reconcile their output. "
        "Return only the required work package. Do not create work items, publish the package, "
        "modify files, or access credentials, environment variables, token caches, or Fabric."
    )
    result = subprocess.run(
        [config.claude_command, "-p", prompt, "--add-dir", str(task_path.parent), "--output-format", "json"],
        cwd=config.repository_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise IssueDispatcherError(
            f"Issue Agent session failed ({session_failure_reason(result.returncode, result.stdout)})"
        )
    try:
        payload = json.loads(result.stdout)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise IssueDispatcherError("Issue Agent session returned invalid output") from error
    if payload.get("is_error"):
        raise IssueDispatcherError(
            f"Issue Agent session failed ({session_failure_reason(result.returncode, result.stdout)})"
        )
    package = payload.get("result")
    if not isinstance(package, str) or not package.strip():
        raise IssueDispatcherError("Issue Agent session returned no work package")
    return package


def run_once(config: IssueDispatcherConfig, state_path: Path, task_directory: Path, dry_run: bool) -> list[dict]:
    state = load_state(state_path)
    tasks = [task for task in discover_once(config) if task["issue"] not in state["dispatched_intakes"]]
    if dry_run or not tasks:
        return tasks
    with session_lock(state_path.with_suffix(".lock")):
        task = tasks[0]
        prepare_issue_clone(config)
        task_directory.mkdir(parents=True, exist_ok=True)
        task_path = task_directory / f"intake-{task['issue']}.json"
        task_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
        package_path = task_path.with_name("work-package.txt")
        package_path.write_text(launch_issue_session(config, task_path), encoding="utf-8")
        subprocess.run(publisher_command(config, task, package_path), cwd=config.repository_path, check=True)
        state["dispatched_intakes"] = [*state["dispatched_intakes"], task["issue"]]
        save_state(state_path, state)
        return [task]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll", action="store_true")
    parser.add_argument("--cycles", type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def report(event: str, **fields) -> None:
    print(json.dumps({"event": event, **fields}), flush=True)


def run_polling_mode(
    config: IssueDispatcherConfig,
    state_path: Path,
    task_directory: Path,
    cycles: int | None,
) -> None:
    run_polling(
        cycle=lambda: run_once(config, state_path, task_directory, dry_run=False),
        poll_seconds=config.poll_seconds,
        errors=(IssueDispatcherError, subprocess.CalledProcessError),
        cycles=cycles,
        on_cycle=lambda tasks: report("poll_completed", issues=[task["issue"] for task in tasks]),
        on_error=lambda error: report("poll_failed", reason=str(error)),
    )


def main() -> int:
    args = parse_args()
    try:
        if sum([args.once, args.poll]) != 1:
            raise IssueDispatcherError("choose exactly one execution mode")
        if args.poll and args.dry_run:
            raise IssueDispatcherError("--poll cannot be combined with --dry-run")

        config = load_config(args.config)
        if args.poll:
            run_polling_mode(config, args.state, args.tasks, args.cycles)
            return 0

        tasks = run_once(config, args.state, args.tasks, args.dry_run)
        if args.dry_run:
            print(json.dumps({"tasks": tasks}))
    except (IssueDispatcherError, PollingStopped) as error:
        print(json.dumps({"error": str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
