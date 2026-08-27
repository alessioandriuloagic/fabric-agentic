"""Publish the Review Agent outcome as a single deterministic GitHub review submission."""

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

from scripts.github_app_auth import (
    GITHUB_API,
    GitHubAppAuthError,
    create_app_jwt,
    create_installation_token,
    load_private_key,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PUBLISHING_BRANCH = "main"
PUBLISHING_REMOTE = "origin"

# Closed checklist of docs/functional/04-checklist-review.md. The publisher does not add items.
CHECKLIST_ITEMS = (
    "A1", "A2", "A3", "A4",
    "B1", "B2", "B3", "B4",
    "C1", "C2", "C3", "C4",
    "D1", "D2", "D3", "D4",
    "E1", "E2", "E3", "E4", "E5",
    "F1", "F2", "F3", "F4",
)

VOTE_EVENTS = {"APPROVATO": "APPROVE", "NON APPROVATO": "REQUEST_CHANGES"}

# The session separates a result from its reason with "-" or "—"; both are accepted, nothing else.
ITEM_PREFIX = re.compile(r"^[A-Z]\d+\b")
ITEM_LINE = re.compile(
    r"^(?P<item>[A-Z]\d+)\s+(?P<result>NON APPLICABILE|PASSATO|RILIEVO)\s*(?:[-—]\s*(?P<detail>.+))?$"
)
VOTE_LINE = re.compile(
    r"^VOTO:\s*(?P<vote>NON APPROVATO|APPROVATO)\s*(?:[-—]\s*(?P<detail>.+))?$"
)

Opener = Callable[[Request], object]
GitRunner = Callable[[list[str]], str]


class ReviewVoteError(Exception):
    """Raised without embedding token, JWT or private-key material."""


@dataclass(frozen=True)
class ReviewOutcome:
    body: str
    event: str
    findings: int


def run_git(arguments: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), *arguments],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ReviewVoteError(f"the publishing copy cannot answer 'git {arguments[0]}'")
    return result.stdout.strip()


def check_publishing_copy(git: GitRunner = run_git) -> None:
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"])
    if branch != PUBLISHING_BRANCH:
        raise ReviewVoteError(f"the publishing copy is on '{branch}', not '{PUBLISHING_BRANCH}'")
    if git(["status", "--porcelain"]):
        raise ReviewVoteError("the publishing copy has uncommitted changes")
    upstream = f"{PUBLISHING_REMOTE}/{PUBLISHING_BRANCH}"
    if git(["rev-parse", "HEAD"]) != git(["rev-parse", upstream]):
        raise ReviewVoteError(f"the publishing copy is not aligned to '{upstream}'")


def read_outcome(outcome_path: Path) -> str:
    try:
        return outcome_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReviewVoteError("the review outcome file is unavailable") from error


def parse_outcome(text: str) -> ReviewOutcome:
    body = text.strip()
    if not body:
        raise ReviewVoteError("the review outcome is empty")

    results: dict[str, str] = {}
    vote: str | None = None
    vote_detail: str | None = None
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("VOTO"):
            if vote is not None:
                raise ReviewVoteError("the review outcome declares more than one VOTO line")
            vote_match = VOTE_LINE.match(line)
            if vote_match is None:
                raise ReviewVoteError("the review outcome has a malformed VOTO line")
            vote, vote_detail = vote_match.group("vote"), vote_match.group("detail")
            continue
        if ITEM_PREFIX.match(line) is None:
            continue
        item_match = ITEM_LINE.match(line)
        if item_match is None:
            raise ReviewVoteError(f"the checklist line '{line.split()[0]}' is malformed")
        item, result = item_match.group("item"), item_match.group("result")
        if item not in CHECKLIST_ITEMS:
            raise ReviewVoteError(f"the review outcome reports the unknown checklist item '{item}'")
        if item in results:
            raise ReviewVoteError(f"the review outcome reports the checklist item '{item}' twice")
        detail = (item_match.group("detail") or "").strip()
        if result == "NON APPLICABILE" and not detail:
            raise ReviewVoteError(f"the checklist item '{item}' is NON APPLICABILE without a reason")
        results[item] = result

    missing = [item for item in CHECKLIST_ITEMS if item not in results]
    if missing:
        raise ReviewVoteError(f"the review outcome misses the checklist items {', '.join(missing)}")
    if vote is None:
        raise ReviewVoteError("the review outcome has no VOTO line")

    findings = sum(1 for result in results.values() if result == "RILIEVO")
    check_vote_consistency(vote, vote_detail, findings)
    return ReviewOutcome(body=body, event=VOTE_EVENTS[vote], findings=findings)


def check_vote_consistency(vote: str, detail: str | None, findings: int) -> None:
    if vote == "APPROVATO":
        if findings:
            raise ReviewVoteError(f"VOTO APPROVATO contradicts {findings} rilievi")
        return
    if not findings:
        raise ReviewVoteError("VOTO NON APPROVATO contradicts an outcome without rilievi")
    declared = re.search(r"\d+", detail or "")
    if declared is None:
        raise ReviewVoteError("VOTO NON APPROVATO does not declare the number of rilievi")
    if int(declared.group()) != findings:
        raise ReviewVoteError(
            f"VOTO NON APPROVATO declares {declared.group()} rilievi instead of {findings}"
        )


def call_api(
    method: str,
    path: str,
    credential: str,
    opener: Opener = urlopen,
    body: dict | None = None,
) -> object:
    request = Request(
        f"{GITHUB_API}{path}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {credential}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with opener(request) as response:
            return json.load(response)
    except Exception as error:
        raise ReviewVoteError(f"GitHub API request failed: {method} {path}") from error


def app_bot_login(app_id: str, key_path: Path, opener: Opener = urlopen) -> str:
    """Return the login the App writes reviews with, so idempotence never depends on extra config."""
    app_jwt = create_app_jwt(app_id, load_private_key(key_path))
    payload = call_api("GET", "/app", app_jwt, opener)
    slug = payload.get("slug") if isinstance(payload, dict) else None
    if not isinstance(slug, str) or not slug:
        raise ReviewVoteError("the GitHub App metadata does not expose the application slug")
    return f"{slug}[bot]"


def pull_request_head_sha(
    owner: str, repository: str, pull_request: int, token: str, opener: Opener = urlopen
) -> str:
    payload = call_api("GET", f"/repos/{owner}/{repository}/pulls/{pull_request}", token, opener)
    head = payload.get("head", {}) if isinstance(payload, dict) else {}
    head_sha = head.get("sha") if isinstance(head, dict) else None
    if not isinstance(head_sha, str) or not head_sha:
        raise ReviewVoteError(f"pull request #{pull_request} does not expose a head sha")
    return head_sha


def has_published_review(
    owner: str,
    repository: str,
    pull_request: int,
    head_sha: str,
    login: str,
    token: str,
    opener: Opener = urlopen,
) -> bool:
    payload = call_api(
        "GET", f"/repos/{owner}/{repository}/pulls/{pull_request}/reviews?per_page=100", token, opener
    )
    reviews = payload if isinstance(payload, list) else []
    return any(
        review.get("commit_id") == head_sha
        and (review.get("user") or {}).get("login") == login
        for review in reviews
    )


def submit_review(
    owner: str,
    repository: str,
    pull_request: int,
    head_sha: str,
    outcome: ReviewOutcome,
    token: str,
    opener: Opener = urlopen,
) -> object:
    return call_api(
        "POST",
        f"/repos/{owner}/{repository}/pulls/{pull_request}/reviews",
        token,
        opener,
        {"commit_id": head_sha, "body": outcome.body, "event": outcome.event},
    )


def publish_review_vote(
    outcome_path: Path,
    owner: str,
    repository: str,
    pull_request: int,
    app_id: str,
    installation_id: str,
    key_path: Path,
    opener: Opener = urlopen,
    git: GitRunner = run_git,
) -> dict:
    check_publishing_copy(git)
    outcome = parse_outcome(read_outcome(outcome_path))

    # Nothing is minted before the copy and the outcome are valid: there are no partial votes.
    login = app_bot_login(app_id, key_path, opener)
    token = create_installation_token(app_id, installation_id, key_path, opener).token
    head_sha = pull_request_head_sha(owner, repository, pull_request, token, opener)

    result = {
        "pull_request": pull_request,
        "head_sha": head_sha,
        "event": outcome.event,
        "rilievi": outcome.findings,
    }
    if has_published_review(owner, repository, pull_request, head_sha, login, token, opener):
        return {**result, "status": "already_published"}
    submit_review(owner, repository, pull_request, head_sha, outcome, token, opener)
    return {**result, "status": "published"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish the Review Agent outcome as one GitHub review submission."
    )
    parser.add_argument("--outcome-path", type=Path, required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pull-request", type=int, required=True)
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--installation-id", required=True)
    parser.add_argument("--key-path", type=Path, required=True)
    return parser.parse_args()


def main(opener: Opener = urlopen, git: GitRunner = run_git) -> int:
    args = parse_args()
    try:
        result = publish_review_vote(
            outcome_path=args.outcome_path,
            owner=args.owner,
            repository=args.repository,
            pull_request=args.pull_request,
            app_id=args.app_id,
            installation_id=args.installation_id,
            key_path=args.key_path,
            opener=opener,
            git=git,
        )
    except (ReviewVoteError, GitHubAppAuthError) as error:
        print(json.dumps({"error": str(error)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
