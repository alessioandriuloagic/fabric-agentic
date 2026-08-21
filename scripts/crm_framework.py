"""Fail-fast CRM configuration checks and OData request construction for the first tracer."""

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_PATH = Path("schemas/crm-source-v1.0.json")


class CrmFrameworkError(ValueError):
    """Raised when CRM tracer configuration or a request boundary is invalid."""


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
    base_url = environment_url.rstrip("/")
    select = "$select=accountid,name,modifiedon"
    if watermark is None:
        return f"{base_url}/api/data/v9.2/accounts?{select}"

    if watermark.tzinfo is None:
        raise CrmFrameworkError("watermark must include a timezone")
    watermark_utc = watermark.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    filter_expression = quote(f"modifiedon ge {watermark_utc}", safe="")
    return f"{base_url}/api/data/v9.2/accounts?{select}&$filter={filter_expression}"
