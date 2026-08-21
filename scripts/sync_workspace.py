"""Synchronize a deterministic feature workspace from its connected Git branch."""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from scripts.branch_out import RailError, derive_names, fabric, fabric_optional


MAX_STATUS_POLLS = 10
STATUS_POLL_SECONDS = 2


def timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def new_result(work_item_id: int, branch_name: str, workspace_name: str) -> dict:
    return {
        "schema_version": "1.2",
        "rail": "sync_workspace",
        "outcome": "technical_failure",
        "run_id": os.getenv("GITHUB_RUN_ID", str(uuid.uuid4())),
        "workspace_id": None,
        "datasets": [],
        "messages": [],
        "sync_workspace": {
            "work_item_id": work_item_id,
            "branch_name": branch_name,
            "workspace_name": workspace_name,
            "status": "not_synchronized",
            "updated_items": [],
            "failure_stage": None,
            "failure_code": None,
        },
        "timestamp": timestamp(),
    }


def write_result(result: dict, output_path: Path) -> None:
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def find_workspace(workspace_name: str) -> dict:
    matches = [
        item
        for item in fabric("GET", "/workspaces").get("value", [])
        if item.get("displayName") == workspace_name
    ]
    if len(matches) != 1 or not matches[0].get("id"):
        raise RailError("workspace")
    return matches[0]


def verify_git_connection(workspace_id: str, branch_name: str) -> None:
    connection = fabric_optional("GET", f"/workspaces/{workspace_id}/git/connection")
    details = connection.get("gitProviderDetails") if connection else None
    expected_owner = os.getenv("FABRIC_GIT_ORGANIZATION", "")
    expected_repository = os.getenv("FABRIC_GIT_REPOSITORY", "")
    if (
        not details
        or details.get("branchName") != branch_name
        or details.get("ownerName") != expected_owner
        or details.get("repositoryName") != expected_repository
    ):
        raise RailError("git_connection")


def changed_item_names(status: dict) -> list[str]:
    names = []
    for change in status.get("changes", []):
        metadata = change.get("itemMetadata", {})
        display_name = metadata.get("displayName")
        if display_name:
            names.append(str(display_name))
    return names


def validate_status(status: dict) -> None:
    changes = status.get("changes", [])
    if any(change.get("conflictType") == "Conflict" for change in changes):
        raise RailError("conflict")
    if any(change.get("workspaceChange") for change in changes):
        raise RailError("divergence")


def is_aligned(status: dict) -> bool:
    return status.get("workspaceHead") == status.get("remoteCommitHash") and not status.get("changes")


def read_status(workspace_id: str) -> dict | None:
    status = fabric("GET", f"/workspaces/{workspace_id}/git/status")
    if not status.get("workspaceHead") and not status.get("remoteCommitHash"):
        return None
    return status


def synchronize(workspace_id: str) -> tuple[str, list[str]]:
    status = None
    for _ in range(MAX_STATUS_POLLS):
        status = read_status(workspace_id)
        if status:
            break
        time.sleep(STATUS_POLL_SECONDS)
    if not status:
        raise RailError("git_status", "operation_timeout")

    validate_status(status)
    if is_aligned(status):
        return "already_aligned", []

    remote_commit = status.get("remoteCommitHash")
    if not remote_commit:
        raise RailError("git_status")
    updated_items = changed_item_names(status)
    fabric(
        "POST",
        f"/workspaces/{workspace_id}/git/updateFromGit",
        {"workspaceHead": status.get("workspaceHead"), "remoteCommitHash": remote_commit},
    )

    for _ in range(MAX_STATUS_POLLS):
        time.sleep(STATUS_POLL_SECONDS)
        status = read_status(workspace_id)
        if not status:
            continue
        validate_status(status)
        if is_aligned(status):
            return "synchronized", updated_items
    raise RailError("sync", "operation_timeout")


def execute(work_item_id: int, slug: str) -> dict:
    branch_name, workspace_name = derive_names(work_item_id, slug)
    result = new_result(work_item_id, branch_name, workspace_name)
    workspace = find_workspace(workspace_name)
    workspace_id = workspace["id"]
    result["workspace_id"] = workspace_id
    verify_git_connection(workspace_id, branch_name)
    status, updated_items = synchronize(workspace_id)
    result["sync_workspace"]["status"] = status
    result["sync_workspace"]["updated_items"] = updated_items
    result["outcome"] = "success"
    result["messages"].append("Workspace is aligned with its connected Git branch.")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-item-id", type=int, required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--output", type=Path, default=Path("rail-result.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    branch_name = f"feature/wi-{args.work_item_id}-{args.slug}"
    workspace_name = f"ws_agentic_feature_wi{args.work_item_id}"
    try:
        result = execute(args.work_item_id, args.slug)
    except (RailError, ValueError) as error:
        result = new_result(args.work_item_id, branch_name, workspace_name)
        result["sync_workspace"]["failure_stage"] = error.stage if isinstance(error, RailError) else "configuration"
        result["sync_workspace"]["failure_code"] = error.failure_code if isinstance(error, RailError) else None
        if isinstance(error, RailError) and error.stage == "conflict":
            result["sync_workspace"]["status"] = "conflict"
        if isinstance(error, RailError) and error.stage == "divergence":
            result["sync_workspace"]["status"] = "divergent"
        result["messages"].append("Workspace synchronization failed; inspect the structured failure stage.")
    except Exception:
        result = new_result(args.work_item_id, branch_name, workspace_name)
        result["sync_workspace"]["failure_stage"] = "unknown"
        result["sync_workspace"]["failure_code"] = "unexpected"
        result["messages"].append("Workspace synchronization failed; inspect the structured failure stage.")
    write_result(result, args.output)
    return 0 if result["outcome"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())