"""Deploy and run the CRM load notebook in a feature workspace."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.crm_framework import CrmFrameworkError, load_configuration
from scripts.fabric_artifacts import notebook_definition
from scripts.fabric_crm_preflight import (
    FabricClient,
    FabricPreflightError,
    access_token,
    find_workspace,
)


LAKEHOUSE_NAME = "lh_bronze_crm_demo"
NOTEBOOK_NAME = "nb_crm_load"
NOTEBOOK_DIRECTORY = Path("fabric/notebook/nb_crm_load.Notebook")


def run_load(work_item_id: int) -> dict:
    configuration = load_configuration(Path("configuration/crm_demo.json"))
    client = FabricClient(access_token())
    workspace = find_workspace(client, work_item_id)
    lakehouse = client.ensure_item(workspace["id"], LAKEHOUSE_NAME, "Lakehouse")
    notebook = client.ensure_item(
        workspace["id"],
        NOTEBOOK_NAME,
        "Notebook",
        notebook_definition(
            NOTEBOOK_DIRECTORY,
            {"id": lakehouse["id"], "displayName": LAKEHOUSE_NAME, "workspace_id": workspace["id"]},
        ),
    )
    client.update_item_definition(
        workspace["id"],
        notebook["id"],
        notebook_definition(
            NOTEBOOK_DIRECTORY,
            {"id": lakehouse["id"], "displayName": LAKEHOUSE_NAME, "workspace_id": workspace["id"]},
        ),
    )
    client.run_notebook(workspace["id"], notebook["id"])
    return {
        "schema_version": "1.0",
        "rail": "run_load",
        "outcome": "success",
        "run_id": f"crm-load-wi{work_item_id}",
        "workspace_id": workspace["id"],
        "datasets": [{
            "name": configuration["datasets"][0]["name"],
            "status": "loaded",
            "source_count": None,
            "destination_count": None,
            "supports_source_count": True,
            "reconciliation": "not_applicable",
            "pk_check": "not_applicable",
        }],
        "messages": ["CRM load notebook completed; notebook evidence is stored in Fabric."],
        "watermark": None,
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
            "schema_version": "1.0",
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