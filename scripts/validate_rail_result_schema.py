"""Validate the invariants of the versioned rail-result contract."""

import json
from pathlib import Path


SCHEMA_PATH = Path("schemas/rail-result-v1.0.json")
BRANCH_OUT_SCHEMA_PATH = Path("schemas/rail-result-v1.1.json")
SYNC_WORKSPACE_SCHEMA_PATH = Path("schemas/rail-result-v1.2.json")
RUN_LOAD_SCHEMA_PATH = Path("schemas/rail-result-v1.3.json")
EXPECTED_RAILS = {"branch_out", "run_load", "sync_workspace", "diagnose_data", "sweep"}
EXPECTED_OUTCOMES = {"success", "technical_failure", "quality_failure"}
REQUIRED_FIELDS = {
    "schema_version",
    "rail",
    "outcome",
    "run_id",
    "workspace_id",
    "datasets",
    "messages",
    "timestamp",
}


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    branch_out_schema = json.loads(BRANCH_OUT_SCHEMA_PATH.read_text(encoding="utf-8"))
    sync_workspace_schema = json.loads(SYNC_WORKSPACE_SCHEMA_PATH.read_text(encoding="utf-8"))
    run_load_schema = json.loads(RUN_LOAD_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["type"] == "object"
    assert set(schema["required"]) == REQUIRED_FIELDS
    assert set(schema["properties"]["rail"]["enum"]) == EXPECTED_RAILS
    assert set(schema["properties"]["outcome"]["enum"]) == EXPECTED_OUTCOMES

    dataset = schema["properties"]["datasets"]["items"]
    assert dataset["properties"]["supports_source_count"]["type"] == "boolean"
    assert dataset["properties"]["reconciliation"]["enum"] == [
        "passed",
        "failed",
        "not_applicable",
    ]

    assert branch_out_schema["properties"]["schema_version"]["const"] == "1.1"
    assert branch_out_schema["properties"]["rail"]["const"] == "branch_out"
    assert branch_out_schema["properties"]["workspace_id"]["type"] == ["string", "null"]
    assert branch_out_schema["properties"]["datasets"]["maxItems"] == 0
    assert set(branch_out_schema["properties"]["branch_out"]["required"]) == {
        "work_item_id",
        "branch_name",
        "workspace_name",
        "branch_status",
        "workspace_status",
        "git_connection_status",
        "sync_status",
        "failure_stage",
        "failure_code",
    }
    assert sync_workspace_schema["properties"]["schema_version"]["const"] == "1.2"
    assert sync_workspace_schema["properties"]["rail"]["const"] == "sync_workspace"
    assert set(sync_workspace_schema["properties"]["sync_workspace"]["required"]) == {
        "work_item_id",
        "branch_name",
        "workspace_name",
        "status",
        "updated_items",
        "failure_stage",
        "failure_code",
    }

    assert run_load_schema["properties"]["schema_version"]["const"] == "1.3"
    assert run_load_schema["properties"]["rail"]["const"] == "run_load"
    assert run_load_schema["properties"]["workspace_id"]["type"] == "string"

    run_load_dataset = run_load_schema["properties"]["datasets"]["items"]
    assert set(run_load_dataset["required"]) == {
        "name",
        "status",
        "loaded_count",
        "total_destination_count",
        "supports_source_count",
        "reconciliation",
        "pk_check",
    }
    assert run_load_dataset["additionalProperties"] is False

    print("rail-result v1.0, v1.1, v1.2, and v1.3 contracts are valid")


if __name__ == "__main__":
    main()
