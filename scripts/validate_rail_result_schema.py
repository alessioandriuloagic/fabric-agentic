"""Validate the invariants of the versioned rail-result contract."""

import json
from pathlib import Path


SCHEMA_PATH = Path("schemas/rail-result-v1.0.json")
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

    print("rail-result v1.0 contract is valid")


if __name__ == "__main__":
    main()
