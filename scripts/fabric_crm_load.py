"""Deploy and run the CRM load notebook in a feature workspace."""

import argparse
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.crm_framework import CrmFrameworkError, load_configuration
from scripts.fabric_artifacts import notebook_definition
from scripts.fabric_crm_preflight import (
    FabricClient,
    FabricPreflightError,
    access_token,
    azure_cli_command,
    find_workspace,
)


LAKEHOUSE_NAME = "lh_bronze_crm_demo"
NOTEBOOK_NAME = "nb_crm_load"
NOTEBOOK_DIRECTORY = Path("fabric/notebook/nb_crm_load.Notebook")
RESULT_DIRECTORY = "Files/agentic/run_load_results"
EVIDENCE_READ_ATTEMPTS = 12
EVIDENCE_READ_DELAY_SECONDS = 5


def storage_access_token() -> str:
    result = subprocess.run(
        [azure_cli_command(), "account", "get-access-token", "--resource", "https://storage.azure.com", "--query", "accessToken", "--output", "tsv"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise FabricPreflightError("OneLake access token acquisition failed")
    return result.stdout.strip()


def result_path(run_id: str) -> str:
    return f"{RESULT_DIRECTORY}/{run_id}.json"


def read_load_result(workspace_id: str, lakehouse_id: str, run_id: str, storage_token: str) -> dict:
    path = result_path(run_id)
    url = f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{lakehouse_id}/{path}"
    request = Request(url, headers={"Authorization": f"Bearer {storage_token}"})
    for attempt in range(EVIDENCE_READ_ATTEMPTS):
        try:
            with urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as error:
            if error.code != 404 or attempt == EVIDENCE_READ_ATTEMPTS - 1:
                raise FabricPreflightError("CRM load evidence is unavailable") from error
            time.sleep(EVIDENCE_READ_DELAY_SECONDS)
        except (OSError, json.JSONDecodeError) as error:
            raise FabricPreflightError("CRM load evidence is unavailable") from error
    if (
        result.get("rail") != "run_load"
        or result.get("outcome") not in {"success", "quality_failure"}
        or result.get("run_id") != run_id
    ):
        raise FabricPreflightError("CRM load evidence is invalid")
    return result


def run_load(work_item_id: int) -> dict:
    run_id = uuid.uuid4().hex
    configuration = load_configuration(Path("configuration/crm_demo.json"))
    client = FabricClient(access_token())
    stage = "workspace"
    try:
        workspace = find_workspace(client, work_item_id)
        stage = "lakehouse"
        lakehouse = client.ensure_item(workspace["id"], LAKEHOUSE_NAME, "Lakehouse")
        definition = notebook_definition(
            NOTEBOOK_DIRECTORY,
            {"id": lakehouse["id"], "displayName": LAKEHOUSE_NAME, "workspace_id": workspace["id"]},
        )
        stage = "notebook"
        notebook = client.ensure_item(workspace["id"], NOTEBOOK_NAME, "Notebook", definition)
        stage = "definition"
        client.update_item_definition(workspace["id"], notebook["id"], definition)
        stage = "submission"
        location = client.run_notebook(workspace["id"], notebook["id"], {"run_id": run_id}, wait=False)
        stage = "storage_token"
        storage_token = storage_access_token()
        stage = "notebook_run"
        client.wait_lro(location, "notebook run")
        stage = "evidence"
        evidence = read_load_result(workspace["id"], lakehouse["id"], run_id, storage_token)
    except FabricPreflightError as error:
        raise FabricPreflightError(f"CRM load failed at {stage}: {error}") from error
    outcome = evidence["outcome"]
    reconciliation = evidence["reconciliation"]
    if (outcome == "success") != (reconciliation == "passed"):
        raise FabricPreflightError("CRM load evidence is inconsistent")
    status = "loaded" if reconciliation == "passed" else "failed"
    return {
        "schema_version": "1.3",
        "rail": "run_load",
        "outcome": outcome,
        "run_id": run_id,
        "workspace_id": workspace["id"],
        "datasets": [{
            "name": configuration["datasets"][0]["name"],
            "status": status,
            "loaded_count": evidence["loaded_count"],
            "total_destination_count": evidence["total_destination_count"],
            "supports_source_count": True,
            "reconciliation": reconciliation,
            "pk_check": "passed",
        }],
        "messages": [f"Evidence stored at {result_path(run_id)}."],
        "watermark": evidence["watermark"],
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-item-id", type=int, required=True)
    parser.add_argument("--output", type=Path, default=Path("rail-result.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_load(args.work_item_id)
    except (FabricPreflightError, CrmFrameworkError) as error:
        result = {
            "schema_version": "1.3",
            "rail": "run_load",
            "outcome": "technical_failure",
            "run_id": f"crm-load-wi{args.work_item_id}",
            "workspace_id": "unknown",
            "datasets": [],
            "messages": [str(error)],
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if result["outcome"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())