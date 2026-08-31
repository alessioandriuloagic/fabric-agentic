"""Backward-compatible entry point; the implementation lives in `fabric_agentic.github_app_auth`."""

from fabric_agentic.github_app_auth import (
    GITHUB_API,
    MINIMUM_PEM_BYTES,
    GitHubAppAuthError,
    InstallationToken,
    create_app_jwt,
    create_installation_token,
    list_installation_repositories,
    load_private_key,
    main,
    request_json,
)

__all__ = [
    "GITHUB_API",
    "MINIMUM_PEM_BYTES",
    "GitHubAppAuthError",
    "InstallationToken",
    "create_app_jwt",
    "create_installation_token",
    "list_installation_repositories",
    "load_private_key",
    "main",
    "request_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
