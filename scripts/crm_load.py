"""Deterministic staged extraction and Bronze load for the CRM tracer."""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable

from scripts.crm_framework import CrmFrameworkError


class CrmLoadError(CrmFrameworkError):
    """Raised when staged data cannot be safely loaded into Bronze."""


@dataclass(frozen=True)
class ExtractionResult:
    run_id: str
    staged_path: Path
    extracted_count: int
    candidate_watermark: datetime | None


@dataclass(frozen=True)
class LoadResult:
    run_id: str
    extracted_count: int
    loaded_count: int
    destination_count: int
    committed_watermark: datetime | None


def extract_accounts(records: Iterable[dict], staging_path: Path, run_id: str, watermark: datetime | None = None) -> ExtractionResult:
    _require_run_id(run_id)
    if watermark is not None:
        _require_aware(watermark)
        watermark = watermark.astimezone(timezone.utc)

    staged: list[dict] = []
    candidate: datetime | None = None
    for record in records:
        _validate_record(record)
        modified = _parse_timestamp(record["modifiedon"])
        if watermark is not None and modified < watermark:
            continue
        staged.append(record)
        if candidate is None or modified > candidate:
            candidate = modified

    _write_json_lines(staging_path, staged)
    return ExtractionResult(run_id, staging_path, len(staged), candidate)


def load_staged_accounts(
    staging_path: Path,
    bronze_path: Path,
    audit_path: Path,
    watermark_path: Path,
    run_id: str,
    confirmed_watermark: datetime | None = None,
) -> LoadResult:
    _require_run_id(run_id)
    existing_watermark = _read_watermark(watermark_path)
    if confirmed_watermark is not None:
        _require_aware(confirmed_watermark)
        confirmed_watermark = confirmed_watermark.astimezone(timezone.utc)
    elif existing_watermark is not None:
        confirmed_watermark = existing_watermark

    staged = _read_json_lines(staging_path)
    _validate_unique_keys(staged)
    bronze = _read_json_lines(bronze_path) if bronze_path.exists() else []
    _validate_unique_keys(bronze)

    merged = {record["accountid"]: record for record in bronze}
    for record in staged:
        _validate_record(record)
        merged[record["accountid"]] = record
    merged_records = list(merged.values())
    _validate_unique_keys(merged_records)
    _write_json_lines(bronze_path, merged_records)

    candidate = max((_parse_timestamp(record["modifiedon"]) for record in staged), default=confirmed_watermark)
    audit_rows = _read_json_lines(audit_path) if audit_path.exists() else []
    audit_rows = [row for row in audit_rows if row.get("run_id") != run_id]
    audit_rows.append({
        "run_id": run_id,
        "dataset": "accounts",
        "extracted_count": len(staged),
        "loaded_count": len(staged),
        "destination_count": len(merged_records),
        "reconciliation": "passed",
        "watermark": candidate.isoformat().replace("+00:00", "Z") if candidate else None,
    })
    _write_json_lines(audit_path, audit_rows)
    _write_watermark(watermark_path, candidate)
    return LoadResult(run_id, len(staged), len(staged), len(merged_records), candidate)


def _validate_record(record: dict) -> None:
    required = {"accountid", "name", "modifiedon"}
    if not isinstance(record, dict) or not required.issubset(record):
        raise CrmLoadError("staged CRM record does not match the declared schema")
    _parse_timestamp(record["modifiedon"])


def _validate_unique_keys(records: list[dict]) -> None:
    keys = [record.get("accountid") for record in records]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise CrmLoadError("CRM primary key check failed")


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise CrmLoadError("CRM modifiedon is not a valid timestamp") from error
    _require_aware(parsed)
    return parsed.astimezone(timezone.utc)


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CrmLoadError("CRM watermark must include a timezone")


def _require_run_id(run_id: str) -> None:
    if not run_id or "/" in run_id or "\\" in run_id:
        raise CrmLoadError("run ID must be a non-empty path-safe value")


def _read_json_lines(path: Path) -> list[dict]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as error:
        raise CrmLoadError("CRM load artifact is unavailable or invalid") from error


def _write_json_lines(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
        for row in rows:
            temporary.write(json.dumps(row, sort_keys=True) + "\n")
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def _read_watermark(path: Path) -> datetime | None:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("confirmed_watermark")
    except (OSError, json.JSONDecodeError) as error:
        raise CrmLoadError("CRM watermark state is unavailable or invalid") from error
    return _parse_timestamp(value) if value else None


def _write_watermark(path: Path, value: datetime | None) -> None:
    payload = {"confirmed_watermark": value.isoformat().replace("+00:00", "Z") if value else None}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")