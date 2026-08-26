"""Deploy and execute the no-record CRM connection preflight in a feature workspace.

Run as ``python -m scripts.fabric_crm_preflight`` so package imports resolve.
"""

import argparse
import json
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.crm_framework import CrmFrameworkError, load_configuration
from scripts.fabric_artifacts import notebook_definition


FABRIC_API = "https://api.fabric.microsoft.com/v1"
LAKEHOUSE_NAME = "lh_bronze_crm_demo"
NOTEBOOK_NAME = "nb_crm_preflight"
NOTEBOOK_DIRECTORY = Path("fabric/notebook/nb_crm_preflight.Notebook")


class FabricPreflightError(RuntimeError):
    """Raised without including access tokens, connection credentials, or response bodies."""


def feature_workspace_name(work_item_id: int) -> str:
    if work_item_id < 1:
        raise FabricPreflightError("work item ID must be positive")
    return f"ws_agentic_feature_wi{work_item_id}"


def access_token() -> str:
    result = subprocess.run(
        ["az", "account", "get-access-token", "--resource", "https://api.fabric.microsoft.com", "--query", "accessToken", "--output", "tsv"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise FabricPreflightError("Fabric access token acquisition failed")
    return result.stdout.strip()


class FabricClient:
    def __init__(self, token: str, opener=urlopen, sleep=time.sleep) -> None:
        self.token = token
        self.opener = opener
        self.sleep = sleep

    def request(self, method: str, path_or_url: str, body: dict | None = None) -> tuple[int, dict, dict]:
        url = path_or_url if path_or_url.startswith("https://") else f"{FABRIC_API}{path_or_url}"
        request = Request(
            url,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with self.opener(request) as response:
                raw = response.read().decode("utf-8")
                return response.status, dict(response.headers), json.loads(raw) if raw else {}
        except HTTPError as error:
            if error.code in {400, 401, 403, 404}:
                raise FabricPreflightError(f"Fabric API request failed with HTTP {error.code}") from error
            raise FabricPreflightError("Fabric API request failed") from error
        except Exception as error:
            raise FabricPreflightError("Fabric API request failed") from error

    def wait_lro(self, location: str, operation_name: str) -> None:
        for _ in range(20):
            status, _, body = self.request("GET", location)
            operation_status = body.get("status")
            if status == 200 and operation_status in {"Succeeded", "Completed"}:
                return
            if operation_status in {"Failed", "Cancelled"}:
                error = body.get("error") if isinstance(body.get("error"), dict) else {}
                error_code = error.get("errorCode") or error.get("code") or "unknown"
                raise FabricPreflightError(
                    f"Fabric {operation_name} failed with status {operation_status} ({error_code})"
                )
            self.sleep(5)
        raise FabricPreflightError(f"Fabric {operation_name} timed out")

    def list_items(self, workspace_id: str, item_type: str) -> list[dict]:
        _, _, body = self.request("GET", f"/workspaces/{workspace_id}/items?type={item_type}")
        return body.get("value", [])

    def ensure_item(self, workspace_id: str, display_name: str, item_type: str, definition: dict | None = None) -> dict:
        matches = [item for item in self.list_items(workspace_id, item_type) if item.get("displayName") == display_name]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise FabricPreflightError("multiple Fabric items match the deterministic name")
        body = {"displayName": display_name, "type": item_type}
        if definition is not None:
            body["definition"] = definition
        status, headers, created = self.request("POST", f"/workspaces/{workspace_id}/items", body)
        if status == 202:
            location = headers.get("Location") or headers.get("location")
            if not location:
                raise FabricPreflightError("Fabric item creation did not return an operation location")
            self.wait_lro(location, "item creation")
            matches = [item for item in self.list_items(workspace_id, item_type) if item.get("displayName") == display_name]
            if len(matches) != 1:
                raise FabricPreflightError("Fabric item creation could not be resolved")
            return matches[0]
        if status != 201 or not created.get("id"):
            raise FabricPreflightError("Fabric item creation failed")
        return created

    def update_item_definition(self, workspace_id: str, item_id: str, definition: dict) -> None:
        status, headers, _ = self.request("POST", f"/workspaces/{workspace_id}/items/{item_id}/updateDefinition", {"definition": definition})
        if status == 202:
            location = headers.get("Location") or headers.get("location")
            if not location:
                raise FabricPreflightError("Fabric item update did not return an operation location")
            self.wait_lro(location, "item definition update")
        elif status != 200:
            raise FabricPreflightError("Fabric item update failed")

    def run_notebook(self, workspace_id: str, notebook_id: str) -> None:
        status, headers, _ = self.request("POST", f"/workspaces/{workspace_id}/items/{notebook_id}/jobs/instances?jobType=RunNotebook")
        if status != 202:
            raise FabricPreflightError("Notebook job submission failed")
        location = headers.get("Location") or headers.get("location")
        if not location:
            raise FabricPreflightError("Notebook job did not return an operation location")
        self.wait_lro(location, "notebook run")


def find_workspace(client: FabricClient, work_item_id: int) -> dict:
    workspace_name = feature_workspace_name(work_item_id)
    _, _, body = client.request("GET", "/workspaces")
    matches = [workspace for workspace in body.get("value", []) if workspace.get("displayName") == workspace_name]
    if len(matches) != 1 or not matches[0].get("id"):
        raise FabricPreflightError("feature workspace is unavailable")
    return matches[0]


def run_preflight(work_item_id: int) -> dict:
    configuration = load_configuration(Path("configuration/crm_demo.json"))
    client = FabricClient(access_token())
    workspace = find_workspace(client, work_item_id)
    lakehouse = client.ensure_item(workspace["id"], LAKEHOUSE_NAME, "Lakehouse")
    definition = notebook_definition(
        NOTEBOOK_DIRECTORY,
        {
            "id": lakehouse["id"],
            "displayName": lakehouse["displayName"],
            "workspace_id": workspace["id"],
        },
    )
    notebook = client.ensure_item(workspace["id"], NOTEBOOK_NAME, "Notebook", definition)
    client.update_item_definition(workspace["id"], notebook["id"], definition)
    client.run_notebook(workspace["id"], notebook["id"])
    return {
        "outcome": "success",
        "work_item_id": work_item_id,
        "workspace_id": workspace["id"],
        "lakehouse_id": lakehouse["id"],
        "notebook_id": notebook["id"],
        "connection_id": configuration["connection_id"],
        "entity_set": configuration["datasets"][0]["entity_set"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-item-id", type=int, required=True)
    parser.add_argument("--output", type=Path, default=Path("crm-preflight-result.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_preflight(args.work_item_id)
    except (FabricPreflightError, CrmFrameworkError) as error:
        result = {"outcome": "technical_failure", "work_item_id": args.work_item_id, "message": str(error)}
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if result["outcome"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
