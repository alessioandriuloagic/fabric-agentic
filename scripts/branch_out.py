"""Provision or reconcile the deterministic Fabric feature workspace for a work item."""

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path


FABRIC_API = "https://api.fabric.microsoft.com/v1"
FOLDERS = [
    "Bronze Layer",
    "Full and Incremental Load",
    "Silver Layer",
    "Semantic Layer",
    "Report",
    "Test Items",
]
SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z",
    re.IGNORECASE,
)


class RailError(Exception):
    """Raised when a deterministic rail step cannot be completed safely."""

    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__(stage)


def derive_names(work_item_id: int, slug: str) -> tuple[str, str]:
    if work_item_id < 1:
        raise ValueError("work_item_id must be a positive integer")
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError("slug must be lowercase kebab-case")
    return f"feature/wi-{work_item_id}-{slug}", f"ws_agentic_feature_wi{work_item_id}"


def require_uuid(name: str, value: str) -> str:
    if not UUID_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a UUID")
    return value


def timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def new_result(work_item_id: int, branch_name: str, workspace_name: str) -> dict:
    return {
        "schema_version": "1.1",
        "rail": "branch_out",
        "outcome": "technical_failure",
        "run_id": os.getenv("GITHUB_RUN_ID", str(uuid.uuid4())),
        "workspace_id": None,
        "datasets": [],
        "messages": [],
        "branch_out": {
            "work_item_id": work_item_id,
            "branch_name": branch_name,
            "workspace_name": workspace_name,
            "branch_status": "not_created",
            "workspace_status": "not_created",
            "git_connection_status": "not_connected",
            "sync_status": "not_synchronized",
            "failure_stage": None,
        },
        "timestamp": timestamp(),
    }


def write_result(result: dict, output_path: Path) -> None:
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def run(command: list[str], input_data: str | None = None) -> str:
    completed = subprocess.run(
        command,
        input=input_data,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RailError("unknown")
    return completed.stdout


def run_optional(command: list[str]) -> str | None:
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode == 0:
        return completed.stdout
    if "404" in completed.stderr or "NotFound" in completed.stderr:
        return None
    raise RailError("unknown")


def fabric(method: str, path: str, body: dict | None = None) -> dict:
    command = [
        "az",
        "rest",
        "--method",
        method,
        "--url",
        f"{FABRIC_API}{path}",
        "--resource",
        "https://api.fabric.microsoft.com",
        "--output",
        "json",
    ]
    if body is not None:
        command.extend(["--body", json.dumps(body)])
    output = run(command)
    return json.loads(output) if output.strip() else {}


def fabric_optional(method: str, path: str) -> dict | None:
    command = [
        "az",
        "rest",
        "--method",
        method,
        "--url",
        f"{FABRIC_API}{path}",
        "--resource",
        "https://api.fabric.microsoft.com",
        "--output",
        "json",
    ]
    output = run_optional(command)
    return json.loads(output) if output and output.strip() else None


def configured_value(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise RailError("configuration")
    return value


def ensure_branch(branch_name: str) -> str:
    remote_ref = f"refs/heads/{branch_name}"
    exists = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", branch_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0
    if exists:
        return "existing"
    run(["git", "push", "origin", f"HEAD:{remote_ref}"])
    return "created"


def find_workspace(workspace_name: str) -> dict | None:
    response = fabric("GET", "/workspaces")
    matches = [item for item in response.get("value", []) if item.get("displayName") == workspace_name]
    if len(matches) > 1:
        raise RailError("workspace")
    return matches[0] if matches else None


def ensure_workspace(workspace_name: str, capacity_id: str) -> tuple[str, str]:
    workspace = find_workspace(workspace_name)
    if workspace:
        workspace_id = workspace.get("id")
        if not workspace_id:
            raise RailError("workspace")
        return workspace_id, "existing"

    workspace = fabric("POST", "/workspaces", {"displayName": workspace_name})
    workspace_id = workspace.get("id")
    if not workspace_id:
        raise RailError("workspace")
    fabric("POST", f"/workspaces/{workspace_id}/assignToCapacity", {"capacityId": capacity_id})
    return workspace_id, "created"


def ensure_owner(workspace_id: str, owner_object_id: str) -> None:
    assignments = fabric("GET", f"/workspaces/{workspace_id}/roleAssignments").get("value", [])
    if any(
        assignment.get("principal", {}).get("id") == owner_object_id
        and assignment.get("role") == "Admin"
        for assignment in assignments
    ):
        return
    fabric(
        "POST",
        f"/workspaces/{workspace_id}/roleAssignments",
        {"principal": {"id": owner_object_id, "type": "User"}, "role": "Admin"},
    )


def ensure_git_connection(workspace_id: str, branch_name: str) -> bool:
    connection_id = configured_value("FABRIC_GIT_CONNECTION_ID")
    organization = configured_value("FABRIC_GIT_ORGANIZATION")
    repository = configured_value("FABRIC_GIT_REPOSITORY")
    existing = fabric_optional("GET", f"/workspaces/{workspace_id}/git/connection")
    if existing:
        details = existing.get("gitProviderDetails")
        if details:
            if (
                details.get("organizationName") != organization
                or details.get("repositoryName") != repository
                or details.get("branchName") != branch_name
            ):
                raise RailError("git_connection")
            return False
    fabric(
        "POST",
        f"/workspaces/{workspace_id}/git/connect",
        {
            "gitProviderDetails": {
                "organizationName": organization,
                "repositoryName": repository,
                "branchName": branch_name,
                "directoryName": "/",
            },
            "myGitCredentials": {"source": "ConfiguredConnection", "connectionId": connection_id},
        },
    )
    return True


def ensure_folders(workspace_id: str) -> None:
    response = fabric("GET", f"/workspaces/{workspace_id}/folders")
    existing = {folder.get("displayName") for folder in response.get("value", [])}
    for folder_name in FOLDERS:
        if folder_name not in existing:
            fabric("POST", f"/workspaces/{workspace_id}/folders", {"displayName": folder_name})


def sync_workspace(workspace_id: str, connection_created: bool) -> None:
    if connection_created:
        fabric("POST", f"/workspaces/{workspace_id}/git/initializeConnection")


def execute(work_item_id: int, slug: str) -> dict:
    branch_name, workspace_name = derive_names(work_item_id, slug)
    result = new_result(work_item_id, branch_name, workspace_name)
    try:
        capacity_id = require_uuid("FABRIC_CAPACITY_ID", configured_value("FABRIC_CAPACITY_ID"))
        owner_object_id = require_uuid("FABRIC_OWNER_OBJECT_ID", configured_value("FABRIC_OWNER_OBJECT_ID"))
    except (RailError, ValueError) as error:
        raise RailError("configuration") from error

    try:
        result["branch_out"]["branch_status"] = ensure_branch(branch_name)
    except RailError as error:
        raise RailError("branch") from error
    try:
        workspace_id, workspace_status = ensure_workspace(workspace_name, capacity_id)
    except RailError as error:
        raise RailError("workspace") from error
    result["workspace_id"] = workspace_id
    result["branch_out"]["workspace_status"] = workspace_status
    try:
        ensure_owner(workspace_id, owner_object_id)
    except RailError as error:
        raise RailError("owner") from error
    try:
        connection_created = ensure_git_connection(workspace_id, branch_name)
    except RailError as error:
        raise RailError("git_connection") from error
    result["branch_out"]["git_connection_status"] = "connected"
    try:
        ensure_folders(workspace_id)
    except RailError as error:
        raise RailError("folders") from error
    try:
        sync_workspace(workspace_id, connection_created)
    except RailError as error:
        raise RailError("sync") from error
    result["branch_out"]["sync_status"] = "synchronized"
    result["outcome"] = "success"
    result["messages"].append("Feature branch and workspace are ready.")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-item-id", type=int, required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--output", type=Path, default=Path("rail-result.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = execute(args.work_item_id, args.slug)
    except (RailError, ValueError) as error:
        branch_name = f"feature/wi-{args.work_item_id}-{args.slug}"
        workspace_name = f"ws_agentic_feature_wi{args.work_item_id}"
        result = new_result(args.work_item_id, branch_name, workspace_name)
        result["branch_out"]["failure_stage"] = error.stage if isinstance(error, RailError) else "configuration"
        result["messages"].append("Branch-out provisioning failed; inspect the structured failure stage.")
    except Exception:
        branch_name = f"feature/wi-{args.work_item_id}-{args.slug}"
        workspace_name = f"ws_agentic_feature_wi{args.work_item_id}"
        result = new_result(args.work_item_id, branch_name, workspace_name)
        result["branch_out"]["failure_stage"] = "unknown"
        result["messages"].append("Branch-out provisioning failed; inspect the structured failure stage.")
    write_result(result, args.output)
    return 0 if result["outcome"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())