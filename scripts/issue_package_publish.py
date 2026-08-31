"""Publish the Issue Agent work package as a single deterministic GitHub comment."""

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

from scripts.github_app_auth import GITHUB_API, create_app_jwt, create_installation_token, load_private_key


IDENTITY_MARKER = "[fabric-agentic-issue-agent]"

# Closed contract of agents/issue/INSTRUCTIONS.md. The publisher does not add sections.
PACKAGE_SECTIONS = (
    "SINTESI",
    "REQUISITI (karl)",
    "ARCHITETTURA (ralph)",
    "RISCHI E DECISIONI",
    "TICKET PROPOSTI",
    "DOMANDE APERTE",
    "APPROVAZIONE RICHIESTA",
)

PACKAGE_MODES = ("Project Bootstrap", "Work Item Design")

HEADER_LINE = re.compile(r"^PACCHETTO DI LAVORO\s*[-—]\s*(?P<mode>.+?)\s*[-—]\s*(?P<subject>.+)$")

Opener = Callable[[Request], object]


class IssuePackageError(Exception):
    """Raised without embedding token, JWT or private-key material."""


@dataclass(frozen=True)
class WorkPackage:
    body: str
    mode: str
    subject: str
    fingerprint: str


def read_package(package_path: Path) -> str:
    try:
        return package_path.read_text(encoding="utf-8")
    except OSError as error:
        raise IssuePackageError("the work package file is unavailable") from error


def parse_package(text: str) -> WorkPackage:
    body = text.strip()
    if not body:
        raise IssuePackageError("the work package is empty")

    lines = body.splitlines()
    header = HEADER_LINE.match(lines[0].strip())
    if header is None:
        raise IssuePackageError("the work package has a malformed header")
    mode = header.group("mode").strip()
    if mode not in PACKAGE_MODES:
        raise IssuePackageError(f"the work package declares the unknown mode '{mode}'")

    positions: dict[str, int] = {}
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if line not in PACKAGE_SECTIONS:
            continue
        if line in positions:
            raise IssuePackageError(f"the work package reports the section '{line}' twice")
        positions[line] = index

    missing = [section for section in PACKAGE_SECTIONS if section not in positions]
    if missing:
        raise IssuePackageError(f"the work package misses the sections {', '.join(missing)}")
    if list(positions) != list(PACKAGE_SECTIONS):
        raise IssuePackageError("the work package sections are out of order")

    check_sections_have_content(lines, positions)
    return WorkPackage(
        body=body,
        mode=mode,
        subject=header.group("subject").strip(),
        fingerprint=hashlib.sha256(body.encode("utf-8")).hexdigest()[:12],
    )


def check_sections_have_content(lines: list[str], positions: dict[str, int]) -> None:
    """`APPROVAZIONE RICHIESTA` closes the package, so only the preceding sections carry content."""
    ordered = list(PACKAGE_SECTIONS)
    for section, following in zip(ordered, ordered[1:]):
        content = lines[positions[section] + 1 : positions[following]]
        if not any(line.strip() for line in content):
            raise IssuePackageError(f"the work package section '{section}' is empty")


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
        raise IssuePackageError(f"GitHub API request failed: {method} {path}") from error


def app_bot_login(app_id: str, key_path: Path, opener: Opener = urlopen) -> str:
    app_jwt = create_app_jwt(app_id, load_private_key(key_path))
    payload = call_api("GET", "/app", app_jwt, opener)
    slug = payload.get("slug") if isinstance(payload, dict) else None
    if not isinstance(slug, str) or not slug:
        raise IssuePackageError("the GitHub App metadata does not expose the application slug")
    return f"{slug}[bot]"


def comment_body(package: WorkPackage) -> str:
    return f"{IDENTITY_MARKER} package {package.fingerprint}\n\n{package.body}"


def has_published_package(
    owner: str,
    repository: str,
    issue: int,
    package: WorkPackage,
    login: str,
    token: str,
    opener: Opener = urlopen,
) -> bool:
    payload = call_api(
        "GET", f"/repos/{owner}/{repository}/issues/{issue}/comments?per_page=100", token, opener
    )
    comments = payload if isinstance(payload, list) else []
    return any(
        (comment.get("user") or {}).get("login") == login
        and f"package {package.fingerprint}" in (comment.get("body") or "")
        for comment in comments
    )


def publish_package(
    package_path: Path,
    owner: str,
    repository: str,
    issue: int,
    app_id: str,
    installation_id: str,
    key_path: Path,
    opener: Opener = urlopen,
) -> dict:
    package = parse_package(read_package(package_path))

    # Nothing is minted before the package is valid: there are no partial publications.
    login = app_bot_login(app_id, key_path, opener)
    token = create_installation_token(app_id, installation_id, key_path, opener).token

    result = {"issue": issue, "mode": package.mode, "fingerprint": package.fingerprint}
    if has_published_package(owner, repository, issue, package, login, token, opener):
        return {**result, "status": "already_published"}
    call_api(
        "POST",
        f"/repos/{owner}/{repository}/issues/{issue}/comments",
        token,
        opener,
        {"body": comment_body(package)},
    )
    return {**result, "status": "published"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish the Issue Agent work package as one GitHub comment."
    )
    parser.add_argument("--package-path", type=Path, required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--installation-id", required=True)
    parser.add_argument("--key-path", type=Path, required=True)
    return parser.parse_args()


def main(opener: Opener = urlopen) -> int:
    args = parse_args()
    try:
        result = publish_package(
            package_path=args.package_path,
            owner=args.owner,
            repository=args.repository,
            issue=args.issue,
            app_id=args.app_id,
            installation_id=args.installation_id,
            key_path=args.key_path,
            opener=opener,
        )
    except IssuePackageError as error:
        print(json.dumps({"error": str(error)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
