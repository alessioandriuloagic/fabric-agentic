"""Fail-fast CRM configuration checks and OData request construction for the first tracer."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from fabric_agentic.connectors import CRM_DATAVERSE, ConnectorError, DatasetRequest, plan_request


SCHEMA_PATH = Path("schemas/crm-source-v1.0.json")
ACCOUNTS = DatasetRequest(
    name="accounts",
    primary_key=("accountid",),
    columns=("accountid", "name", "modifiedon"),
    watermark_column="modifiedon",
)


class CrmFrameworkError(ValueError):
    """Raised when CRM tracer configuration or a request boundary is invalid."""


@dataclass(frozen=True)
class LoadPlan:
    request_url: str
    merge_key: str
    candidate_watermark: datetime | None


def plan_accounts_load(environment_url: str, confirmed_watermark: datetime | None, observed_maximum: datetime | None) -> LoadPlan:
    if observed_maximum is not None and observed_maximum.tzinfo is None:
        raise CrmFrameworkError("observed watermark must include a timezone")
    return LoadPlan(
        request_url=build_accounts_request(environment_url, confirmed_watermark),
        merge_key="accountid",
        candidate_watermark=observed_maximum.astimezone(timezone.utc) if observed_maximum else None,
    )


def commit_watermark(plan: LoadPlan, bronze_merged: bool, audit_written: bool) -> datetime | None:
    if not bronze_merged or not audit_written:
        raise CrmFrameworkError("watermark cannot advance before Bronze merge and audit commit")
    return plan.candidate_watermark


def load_configuration(configuration_path: Path, schema_path: Path = SCHEMA_PATH) -> dict:
    try:
        configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CrmFrameworkError("CRM configuration is unavailable or invalid JSON") from error

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(configuration), key=lambda error: list(error.path))
    if errors:
        raise CrmFrameworkError("CRM configuration fails the v1.0 contract")
    return configuration


def build_accounts_request(environment_url: str, watermark: datetime | None) -> str:
    try:
        plan = plan_request(CRM_DATAVERSE.name, {"environment_url": environment_url}, ACCOUNTS, watermark)
    except ConnectorError as error:
        raise CrmFrameworkError(str(error)) from error
    return plan.target
