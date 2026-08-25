"""Create short-lived GitHub App installation tokens for the Dev Agent."""

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

import jwt


GITHUB_API = "https://api.github.com"
MINIMUM_PEM_BYTES = 256


class GitHubAppAuthError(Exception):
    """Raised without embedding private-key or token material."""


@dataclass(frozen=True)
class InstallationToken:
    token: str
    expires_at: str


def load_private_key(key_path: Path) -> str:
    try:
        if key_path.stat().st_size < MINIMUM_PEM_BYTES:
            raise GitHubAppAuthError("GitHub App PEM is missing or too small")
        return key_path.read_text(encoding="utf-8")
    except OSError as error:
        raise GitHubAppAuthError("GitHub App PEM is unavailable") from error


def create_app_jwt(app_id: str, private_key: str, now: int | None = None) -> str:
    issued_at = int(time.time()) if now is None else now
    try:
        return jwt.encode(
            {"iat": issued_at - 60, "exp": issued_at + 540, "iss": str(app_id)},
            private_key,
            algorithm="RS256",
        )
    except Exception as error:
        raise GitHubAppAuthError("GitHub App PEM cannot sign a JWT") from error


def request_json(request: Request, opener: Callable[[Request], object] = urlopen) -> dict:
    try:
        with opener(request) as response:
            return json.load(response)
    except Exception as error:
        raise GitHubAppAuthError("GitHub App API request failed") from error


def create_installation_token(
    app_id: str,
    installation_id: str,
    key_path: Path,
    opener: Callable[[Request], object] = urlopen,
) -> InstallationToken:
    app_jwt = create_app_jwt(app_id, load_private_key(key_path))
    request = Request(
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        data=b"{}",
        method="POST",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    response = request_json(request, opener)
    token = response.get("token")
    expires_at = response.get("expires_at")
    if not isinstance(token, str) or not isinstance(expires_at, str):
        raise GitHubAppAuthError("GitHub App API returned an invalid installation token")
    return InstallationToken(token=token, expires_at=expires_at)


def list_installation_repositories(
    installation_token: str,
    opener: Callable[[Request], object] = urlopen,
) -> list[str]:
    request = Request(
        f"{GITHUB_API}/installation/repositories",
        headers={
            "Authorization": f"Bearer {installation_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    response = request_json(request, opener)
    return [repository["full_name"] for repository in response.get("repositories", [])]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--installation-id", required=True)
    parser.add_argument("--key-path", type=Path, required=True)
    parser.add_argument("verify", nargs="?")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        installation_token = create_installation_token(args.app_id, args.installation_id, args.key_path)
        if args.verify:
            print(json.dumps({"repositories": list_installation_repositories(installation_token.token)}))
    except GitHubAppAuthError as error:
        print(json.dumps({"error": str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())