"""Build Fabric item-definition payloads from versioned Git artifact sources."""

import base64
from pathlib import Path


class FabricArtifactError(ValueError):
    """Raised when a versioned Fabric artifact is incomplete or unsafe to deploy."""


def notebook_definition(notebook_directory: Path) -> dict:
    source_path = notebook_directory / "notebook-content.py"
    platform_path = notebook_directory / ".platform"
    if not source_path.exists() or not platform_path.exists():
        raise FabricArtifactError("notebook source or platform metadata is missing")

    source = source_path.read_text(encoding="utf-8")
    platform = platform_path.read_text(encoding="utf-8")
    if "# Fabric notebook source" not in source or "# CELL ********************" not in source:
        raise FabricArtifactError("notebook source is not FabricGitSource format")
    if '"type": "Notebook"' not in platform:
        raise FabricArtifactError("platform metadata is not a Notebook")

    return {
        "format": "FabricGitSource",
        "parts": [
            {
                "path": "notebook-content.py",
                "payload": base64.b64encode(source.encode("utf-8")).decode("ascii"),
                "payloadType": "InlineBase64",
            },
            {
                "path": ".platform",
                "payload": base64.b64encode(platform.encode("utf-8")).decode("ascii"),
                "payloadType": "InlineBase64",
            },
        ],
    }
