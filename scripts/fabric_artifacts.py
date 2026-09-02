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
    lakehouse_metadata = {}
    if default_lakehouse is not None:
        required = {"id", "displayName", "workspace_id"}
        if not required.issubset(default_lakehouse):
            raise FabricArtifactError("default Lakehouse metadata is incomplete")
        lakehouse_metadata = {
            "dependencies": {
                "lakehouse": {
                    "default_lakehouse": default_lakehouse["id"],
                    "default_lakehouse_name": default_lakehouse["displayName"],
                    "default_lakehouse_workspace_id": default_lakehouse["workspace_id"],
                }
            }
        }

    cells = []
    for cell_source in source.split("# CELL ********************")[1:]:
        code = cell_source.split("# METADATA ********************", 1)[0].strip("\n")
        if code.strip():
            cells.append({
                "cell_type": "code",
                "execution_count": None,
                "metadata": {"tags": ["parameters"]} if code.startswith("# PARAMETERS CELL") else {},
                "outputs": [],
                "source": [f"{line}\n" for line in code.splitlines()],
            })
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "language_info": {"name": "python"},
            "kernelspec": {"display_name": "Synapse PySpark", "language": "python", "name": "synapse_pyspark"},
            **lakehouse_metadata,
        },
        "cells": cells,
    }

    return {
        "format": "ipynb",
        "parts": [
            {
                "path": "notebook-content.ipynb",
                "payload": base64.b64encode(json.dumps(notebook, separators=(",", ":")).encode("utf-8")).decode("ascii"),
                "payloadType": "InlineBase64",
            },
        ],
    }
