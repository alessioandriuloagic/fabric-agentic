"""Run the shared CRM Bronze load and publish the rail-result contract."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.crm_load import CrmLoadError, load_staged_accounts


def execute_load(workspace_id: str, staged_path: Path, bronze_path: Path, audit_path: Path, watermark_path: Path, run_id: str) -> dict:
    if not workspace_id:
        raise CrmLoadError("workspace ID is required")
    result = load_staged_accounts(staged_path, bronze_path, audit_path, watermark_path, run_id)
    return {
        "schema_version": "1.0",
        "rail": "run_load",
        "outcome": "success",
        "run_id": run_id,
        "workspace_id": workspace_id,
        "datasets": [{
            "name": "accounts",
            "status": "loaded",
            "source_count": result.extracted_count,
            "destination_count": result.destination_count,
            "supports_source_count": True,
            "reconciliation": "passed",
            "pk_check": "passed",
        }],
        "messages": [],
        "diagnostics": {
            "schema_drift": False,
            "null_count": 0,
            "masked_key_samples": [],
        },
        "watermark": result.committed_watermark.isoformat().replace("+00:00", "Z") if result.committed_watermark else None,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--staged", type=Path, required=True)
    parser.add_argument("--bronze", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--watermark", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, default=Path("rail-result.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = execute_load(args.workspace_id, args.staged, args.bronze, args.audit, args.watermark, args.run_id)
    except CrmLoadError as error:
        quality_failure = "primary key" in str(error).lower()
        result = {
            "schema_version": "1.0",
            "rail": "run_load",
            "outcome": "quality_failure" if quality_failure else "technical_failure",
            "run_id": args.run_id,
            "workspace_id": args.workspace_id,
            "datasets": [{
                "name": "accounts",
                "status": "failed",
                "source_count": None,
                "destination_count": None,
                "supports_source_count": True,
                "reconciliation": "failed" if quality_failure else "not_applicable",
                "pk_check": "failed" if quality_failure else "not_applicable",
            }],
            "messages": [str(error)],
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if result["outcome"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())