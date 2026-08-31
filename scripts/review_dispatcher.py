"""Deterministic dispatcher for fresh Review Agent sessions."""

import argparse
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.github_app_auth import GITHUB_API, create_installation_token
from scripts.review_vote_publish import app_bot_login


PUBLISHER_MODULE = "scripts.review_vote_publish"


class ReviewDispatcherError(Exception):
    """Raised without including credentials or response bodies."""


@dataclass(frozen=True)
class ReviewDispatcherConfig:
    github_owner: str
    github_repository: str
    github_app_id: int
    github_installation_id: int
    github_private_key_path: Path
    repository_path: Path
    claude_command: str
    poll_seconds: int = 30


@dataclass(frozen=True)
class PullRequestCandidate:
    number: int
    head_sha: str
    title: str
    url: str


def load_config(config_path: Path) -> ReviewDispatcherConfig:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        github = config["github"]
        agent = config["agent"]
        return ReviewDispatcherConfig(
            github_owner=github["owner"],
            github_repository=github["repository"],
            github_app_id=int(github["app_id"]),
            github_installation_id=int(github["installation_id"]),
            github_private_key_path=expand_path(github["private_key_path"]),
            repository_path=expand_path(agent["repository_path"]),
            claude_command=agent["claude_command"],
            poll_seconds=int(agent.get("poll_seconds", 30)),
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ReviewDispatcherError("review dispatcher configuration is invalid") from error


def expand_path(value: str) -> Path:
    path = Path(os.path.expandvars(value)).expanduser()
    return path


def github_request(method: str, path: str, token: str, body: dict | None = None) -> object:
    request = Request(
        f"{GITHUB_API}{path}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
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
        raise ReviewDispatcherError(f"GitHub review discovery failed: {method} {path}") from error


def open_pull_requests(config: ReviewDispatcherConfig, token: str) -> list[dict]:
    payload = github_request(
        "GET",
        f"/repos/{config.github_owner}/{config.github_repository}/pulls?state=open&per_page=100",
        token,
    )
    return payload if isinstance(payload, list) else []


def pull_request_reviews(config: ReviewDispatcherConfig, number: int, token: str) -> list[dict]:
    payload = github_request(
        "GET",
        f"/repos/{config.github_owner}/{config.github_repository}/pulls/{number}/reviews?per_page=100",
        token,
    )
    return payload if isinstance(payload, list) else []


def review_candidates(config: ReviewDispatcherConfig, token: str, review_login: str) -> list[PullRequestCandidate]:
    candidates = []
    for pull_request in open_pull_requests(config, token):
        if pull_request.get("draft"):
            continue
        number = pull_request.get("number")
        head_sha = pull_request.get("head", {}).get("sha")
        if not isinstance(number, int) or not isinstance(head_sha, str) or not head_sha:
            continue
        reviews = pull_request_reviews(config, number, token)
        reviewed_head = any(
            review.get("commit_id") == head_sha
            and (review.get("user") or {}).get("login") == review_login
            for review in reviews
        )
        if not reviewed_head:
            candidates.append(
                PullRequestCandidate(
                    number=number,
                    head_sha=head_sha,
                    title=str(pull_request.get("title", "")),
                    url=str(pull_request.get("html_url", "")),
                )
            )
    return candidates


@contextmanager
def session_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise ReviewDispatcherError("a Review Agent session is already active") from error
    try:
        os.close(descriptor)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def task_record(config: ReviewDispatcherConfig, candidate: PullRequestCandidate) -> dict:
    return {
        "pull_request": candidate.number,
        "head_sha": candidate.head_sha,
        "pull_request_url": candidate.url,
        "title": candidate.title,
        "repository_path": str(config.repository_path),
        "trigger": "pull_request_review",
    }


def run_git(config: ReviewDispatcherConfig, arguments: list[str]) -> None:
    result = subprocess.run(
        ["git", "-C", str(config.repository_path), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReviewDispatcherError(f"the review clone cannot answer 'git {arguments[0]}'")


def prepare_review_clone(config: ReviewDispatcherConfig, pull_request: int) -> str:
    """Fetch the pull request head without leaving main, so the publisher copy stays aligned."""
    head_ref = f"refs/remotes/origin/pr/{pull_request}"
    run_git(config, ["fetch", "--prune", "origin", "main"])
    run_git(config, ["checkout", "main"])
    run_git(config, ["merge", "--ff-only", "origin/main"])
    run_git(config, ["fetch", "--force", "origin", f"pull/{pull_request}/head:{head_ref}"])
    return head_ref


def publisher_command(config: ReviewDispatcherConfig, task: dict, outcome_path: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        PUBLISHER_MODULE,
        "--outcome-path", str(outcome_path),
        "--owner", config.github_owner,
        "--repository", config.github_repository,
        "--pull-request", str(task["pull_request"]),
        "--app-id", str(config.github_app_id),
        "--installation-id", str(config.github_installation_id),
        "--key-path", str(config.github_private_key_path),
    ]


def load_state(state_path: Path) -> dict[str, dict[str, str]]:
    if not state_path.exists():
        return {"reviewed_heads": {}}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
        reviewed_heads = state.get("reviewed_heads", {})
        if not isinstance(reviewed_heads, dict):
            raise ValueError
        return {"reviewed_heads": reviewed_heads}
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ReviewDispatcherError("review dispatcher state is invalid") from error


def save_state(state_path: Path, state: dict[str, dict[str, str]]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = state_path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(state_path)


def discover_once(config: ReviewDispatcherConfig) -> list[dict]:
    token = create_installation_token(
        config.github_app_id,
        config.github_installation_id,
        config.github_private_key_path,
    ).token
    login = app_bot_login(str(config.github_app_id), config.github_private_key_path)
    candidates = review_candidates(config, token, login)
    return [task_record(config, candidate) for candidate in candidates]


def launch_review_session(config: ReviewDispatcherConfig, task_path: Path) -> str:
    prompt = (
        "You are a fresh Review Agent session. Read the task record at "
        f"{task_path}, then review exactly that pull request and follow .github/agents/review-agent.agent.md. "
        "The dispatcher already fetched the pull request head into the clone: inspect the diff with "
        "git commands such as 'git diff origin/main...<head_ref>' and 'git show <head_sha>'. "
        "Return only the required A1-F4 structured outcome. Do not publish the review, modify files, "
        "access credentials, environment variables, certificate stores, token caches, or Fabric."
    )
    result = subprocess.run(
        [config.claude_command, "-p", prompt, "--add-dir", str(task_path.parent), "--output-format", "json"],
        cwd=config.repository_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise ReviewDispatcherError("Review Agent session failed")
    try:
        payload = json.loads(result.stdout)
        outcome = payload.get("result")
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ReviewDispatcherError("Review Agent session returned invalid output") from error
    if not isinstance(outcome, str) or not outcome.strip():
        raise ReviewDispatcherError("Review Agent session returned no outcome")
    return outcome


def run_once(config: ReviewDispatcherConfig, state_path: Path, task_directory: Path, dry_run: bool) -> list[dict]:
    state = load_state(state_path)
    tasks = [
        task for task in discover_once(config)
        if state["reviewed_heads"].get(str(task["pull_request"])) != task["head_sha"]
    ]
    if dry_run or not tasks:
        return tasks
    with session_lock(state_path.with_suffix(".lock")):
        task = tasks[0]
        task["head_ref"] = prepare_review_clone(config, task["pull_request"])
        task_directory.mkdir(parents=True, exist_ok=True)
        task_path = task_directory / f"review-{task['pull_request']}-{task['head_sha']}.json"
        task_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
        outcome_path = task_path.with_name("review-outcome.txt")
        outcome_path.write_text(launch_review_session(config, task_path), encoding="utf-8")
        subprocess.run(
            publisher_command(config, task, outcome_path),
            cwd=config.repository_path,
            check=True,
        )
        state["reviewed_heads"][str(task["pull_request"])] = task["head_sha"]
        save_state(state_path, state)
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
        if not args.once:
            raise ReviewDispatcherError("choose --once")
        tasks = run_once(load_config(args.config), args.state, args.tasks, args.dry_run)
        if args.dry_run:
            print(json.dumps({"tasks": tasks}))
    except ReviewDispatcherError as error:
        print(json.dumps({"error": str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())