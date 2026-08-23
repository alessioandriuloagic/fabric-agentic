"""Build Fabric item-definition payloads from versioned Git artifact sources."""

import base64
import json
from pathlib import Path


class FabricArtifactError(ValueError):
    """Raised when a versioned Fabric artifact is incomplete or unsafe to deploy."""


def notebook_definition(notebook_directory: Path, default_lakehouse: dict | None = None) -> dict:
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
    if default_lakehouse is not None:
        required = {"id", "displayName", "workspace_id"}
        if not required.issubset(default_lakehouse):
            raise FabricArtifactError("default Lakehouse metadata is incomplete")
        dependencies = {
            "lakehouse": {
                "default_lakehouse": default_lakehouse["id"],
                "default_lakehouse_name": default_lakehouse["displayName"],
                "default_lakehouse_workspace_id": default_lakehouse["workspace_id"],
            }
        }
        source = source.replace('"dependencies": {}', f'"dependencies": {json.dumps(dependencies, separators=(",", ":"))}')

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
