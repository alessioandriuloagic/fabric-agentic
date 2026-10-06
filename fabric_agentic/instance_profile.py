"""Portable instance profile: one client or project deployment, without secrets."""

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from fabric_agentic.connectors import (
    ConnectorError,
    connector_names,
    get_connector,
    suggested_connector_names,
)


SUPPORTED_SCHEMA_VERSIONS = ("1.0",)
SUPPORTED_TRACKERS = ("github_issues", "azure_devops")
LOAD_MODES = ("full", "incremental")
AGENT_ROLES = ("issue", "dev", "review")
TRACKER_AUTH_MODES = {"github_issues": ("github_app", "github_user"), "azure_devops": ("entra_sp", "entra_user")}

SLUG = re.compile(r"^[a-z][a-z0-9_]*$")
SECRET_FIELDS = ("value", "secret", "password", "token", "client_secret")


def profile_schema() -> dict:
    connectors = [get_connector(name) for name in connector_names()]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://fabric-agentic.local/schemas/instance-profile-v1.0.json",
        "title": "Fabric Agentic instance profile",
        "type": "object",
        "required": ["schema_version", "project", "tracker", "environments", "sources", "credentials"],
        "properties": {
            "schema_version": {"const": SUPPORTED_SCHEMA_VERSIONS[0]},
            "project": {
                "type": "object",
                "required": ["slug", "display_name"],
                "properties": {
                    "slug": {"type": "string", "pattern": SLUG.pattern},
                    "display_name": {"type": "string", "minLength": 1},
                },
            },
            "tracker": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"enum": list(SUPPORTED_TRACKERS)},
                    "authentication": {
                        "type": "object", "minProperties": 1,
                        "propertyNames": {"enum": list(AGENT_ROLES)},
                        "additionalProperties": {"$ref": "#/$defs/tracker_auth"},
                    },
                },
                "allOf": [
                    {"if": {"properties": {"type": {"const": tracker}}},
                     "then": {"properties": {"authentication": {"additionalProperties": {
                         "properties": {"mode": {"enum": list(modes)}},
                     }}}}}
                    for tracker, modes in TRACKER_AUTH_MODES.items()
                ],
            },
            "environments": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "sources": {"type": "array", "items": {"$ref": "#/$defs/source"}},
            "credentials": {"type": "array", "items": {"$ref": "#/$defs/credential"}},
            "execution": {"$ref": "#/$defs/execution"},
            "inference": {
                "type": "object", "minProperties": 1,
                "propertyNames": {"enum": list(AGENT_ROLES)},
                "additionalProperties": {
                    "type": "object", "additionalProperties": False,
                    "required": ["command", "identity_ref"],
                    "properties": {"command": {"type": "string", "minLength": 1},
                                   "identity_ref": {"type": "string", "minLength": 1}},
                },
            },
        },
        "$defs": {
            "tracker_auth": {"oneOf": [
                {"type": "object", "additionalProperties": False,
                 "required": ["mode"], "properties": {"mode": {"const": mode}}}
                for mode in ("github_app", "entra_sp")
            ] + [
                {"type": "object", "additionalProperties": False,
                 "required": ["mode", "account", "config_directory"] + (["tenant_id"] if mode == "entra_user" else []),
                 "properties": {"mode": {"const": mode},
                                "account": {"type": "string", "minLength": 1},
                                "config_directory": {"type": "string", "minLength": 1},
                                **({"tenant_id": {"type": "string", "format": "uuid"}} if mode == "entra_user" else {})}}
                for mode in ("github_user", "entra_user")
            ]},
            "execution": {
                "type": "object",
                "additionalProperties": False,
                "required": ["mode", "tenant_id", "workspace_id", "account"],
                "properties": {
                    "mode": {"const": "delegated_assisted"},
                    "tenant_id": {"type": "string", "format": "uuid"},
                    "workspace_id": {"type": "string", "format": "uuid"},
                    "account": {"type": "string", "minLength": 1},
                },
            },
            "source": {
                "type": "object",
                "required": ["name", "connector", "connection_ref", "datasets"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "connector": {"type": "string", "pattern": SLUG.pattern},
                    "connection_ref": {"type": "string", "minLength": 1},
                    "capabilities": {"$ref": "#/$defs/capabilities"},
                    "datasets": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/dataset"}},
                },
            },
            "capabilities": {
                "type": "object",
                "required": ["supports_incremental", "supports_source_count"],
                "properties": {
                    "supports_incremental": {"type": "boolean"},
                    "supports_source_count": {"type": "boolean"},
                },
            },
            "dataset": {
                "type": "object",
                "required": ["name", "primary_key", "load_mode"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "primary_key": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 1},
                    },
                    "load_mode": {"enum": list(LOAD_MODES)},
                    "watermark_column": {"type": ["string", "null"]},
                },
            },
            "credential": {
                "type": "object",
                "required": ["name", "store", "reference"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "store": {"type": "string", "minLength": 1},
                    "reference": {"type": "string", "minLength": 1},
                },
            },
        },
        "x-fabric-agentic": {
            "suggested_connectors": list(suggested_connector_names()),
            "connectors": {
                connector.name: {
                    "supports_incremental": connector.supports_incremental,
                    "supports_source_count": connector.supports_source_count,
                    "connection_fields": list(connector.connection_fields),
                }
                for connector in connectors
            },
            "forbidden_credential_fields": list(SECRET_FIELDS),
        },
    }


class InstanceProfileError(Exception):
    """Raised without embedding credential material."""


@dataclass(frozen=True)
class Dataset:
    name: str
    primary_key: tuple[str, ...]
    load_mode: str
    watermark_column: str | None


@dataclass(frozen=True)
class Source:
    name: str
    connector: str
    connection_ref: str
    supports_incremental: bool
    supports_source_count: bool
    adapter_available: bool
    datasets: tuple[Dataset, ...]


@dataclass(frozen=True)
class CredentialRef:
    name: str
    store: str
    reference: str


@dataclass(frozen=True)
class UserExecution:
    mode: str
    tenant_id: str
    workspace_id: str
    account: str


@dataclass(frozen=True)
class InstanceProfile:
    schema_version: str
    project_slug: str
    display_name: str
    tracker_type: str
    tracker: dict
    environments: tuple[str, ...]
    sources: tuple[Source, ...]
    credentials: tuple[CredentialRef, ...]
    execution: UserExecution | None = None
    inference: dict | None = None


def load_profile(profile_path: Path) -> InstanceProfile:
    try:
        document = json.loads(profile_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise InstanceProfileError("the instance profile is unreadable") from error
    return parse_profile(document)


def parse_profile(document: dict) -> InstanceProfile:
    if not isinstance(document, dict):
        raise InstanceProfileError("the instance profile must be an object")

    version = document.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise InstanceProfileError(f"unsupported schema version '{version}'")

    project = document.get("project") or {}
    slug = project.get("slug")
    if not isinstance(slug, str) or not SLUG.match(slug):
        raise InstanceProfileError("the project slug must be lowercase alphanumeric with underscores")

    tracker = document.get("tracker") or {}
    if tracker.get("type") not in SUPPORTED_TRACKERS:
        raise InstanceProfileError(f"unsupported tracker '{tracker.get('type')}'")
    tracker = dict(tracker)
    if "authentication" in tracker:
        identities = tracker["authentication"]
        if not isinstance(identities, dict) or not identities or set(identities) - set(AGENT_ROLES):
            raise InstanceProfileError("tracker authentication requires known agent roles")
        tracker["authentication"] = {}
        for role, identity in identities.items():
            if identity is None:
                raise InstanceProfileError("tracker role authentication must be explicit")
            tracker["authentication"][role] = parse_tracker_auth(identity, tracker["type"])

    environments = document.get("environments") or []
    if not isinstance(environments, list) or not environments:
        raise InstanceProfileError("the profile must declare at least one environment")

    return InstanceProfile(
        schema_version=version,
        project_slug=slug,
        display_name=str(project.get("display_name", slug)),
        tracker_type=tracker["type"],
        tracker=tracker,
        environments=tuple(str(environment) for environment in environments),
        sources=parse_sources(document.get("sources") or []),
        credentials=parse_credentials(document.get("credentials") or []),
        execution=parse_execution(document["execution"]) if "execution" in document else None,
        inference=parse_inference(document["inference"]) if "inference" in document else None,
    )


def parse_inference(document: dict) -> dict:
    if not isinstance(document, dict) or not document or set(document) - set(AGENT_ROLES):
        raise InstanceProfileError("inference requires known agent roles")
    parsed = {}
    for role, identity in document.items():
        if not isinstance(identity, dict) or set(identity) != {"command", "identity_ref"}:
            raise InstanceProfileError("inference requires only command and identity_ref")
        if any(not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value for value in identity.values()):
            raise InstanceProfileError("inference requires nonempty runtime references")
        parsed[role] = {name: value.strip() for name, value in identity.items()}
    return parsed


def parse_execution(document: dict) -> UserExecution:
    required = {"mode", "tenant_id", "workspace_id", "account"}
    if not isinstance(document, dict) or set(document) != required:
        raise InstanceProfileError("execution must contain only mode, tenant_id, workspace_id and account")
    if document["mode"] != "delegated_assisted":
        raise InstanceProfileError("execution requires delegated_assisted mode")
    try:
        tenant_id = str(uuid.UUID(document["tenant_id"]))
        workspace_id = str(uuid.UUID(document["workspace_id"]))
    except (ValueError, TypeError, AttributeError) as error:
        raise InstanceProfileError("execution requires valid tenant and workspace UUIDs") from error
    account = document["account"]
    if not isinstance(account, str) or not account.strip() or account.startswith("-"):
        raise InstanceProfileError("execution requires an account name")
    return UserExecution(document["mode"], tenant_id, workspace_id, account.strip())


def parse_tracker_auth(document: dict | None, tracker_type: str) -> dict | None:
    if document is None:
        return None
    if not isinstance(document, dict) or document.get("mode") not in TRACKER_AUTH_MODES.get(tracker_type, ()):
        raise InstanceProfileError("tracker authentication mode is incompatible with the tracker")
    mode = document["mode"]
    required = {"mode"}
    if mode in ("github_user", "entra_user"):
        required.update(("account", "config_directory"))
    if mode == "entra_user":
        required.add("tenant_id")
    if set(document) != required:
        raise InstanceProfileError("tracker authentication contains missing or unsupported fields")
    parsed = dict(document)
    for name in required - {"mode"}:
        value = parsed[name]
        if not isinstance(value, str) or not value.strip() or value.startswith("-") or "\n" in value or "\r" in value:
            raise InstanceProfileError("tracker authentication requires valid context references")
        parsed[name] = value.strip()
    if mode == "entra_user":
        try:
            parsed["tenant_id"] = str(uuid.UUID(parsed["tenant_id"]))
        except ValueError as error:
            raise InstanceProfileError("tracker authentication requires a tenant UUID") from error
    return parsed


def parse_sources(sources: list) -> tuple[Source, ...]:
    parsed = []
    seen_datasets: set[str] = set()
    for source in sources:
        connector = source.get("connector")
        if not isinstance(connector, str) or not SLUG.match(connector):
            raise InstanceProfileError("the connector must be lowercase alphanumeric with underscores")
        supports_incremental, supports_source_count, adapter_available = _source_capabilities(source, connector)
        if not source.get("connection_ref"):
            raise InstanceProfileError(f"the source '{source.get('name')}' must reference a connection")
        parsed.append(
            Source(
                name=str(source.get("name")),
                connector=connector,
                connection_ref=str(source["connection_ref"]),
                supports_incremental=supports_incremental,
                supports_source_count=supports_source_count,
                adapter_available=adapter_available,
                datasets=parse_datasets(
                    source.get("datasets") or [], connector, supports_incremental, seen_datasets
                ),
            )
        )
    return tuple(parsed)


def _source_capabilities(source: dict, connector_name: str) -> tuple[bool, bool, bool]:
    try:
        adapter = get_connector(connector_name)
    except ConnectorError:
        capabilities = source.get("capabilities")
        if not isinstance(capabilities, dict) or not all(
            isinstance(capabilities.get(name), bool)
            for name in ("supports_incremental", "supports_source_count")
        ):
            raise InstanceProfileError(
                f"the connector '{connector_name}' must declare capabilities because no adapter is registered"
            ) from None
        return capabilities["supports_incremental"], capabilities["supports_source_count"], False
    return adapter.supports_incremental, adapter.supports_source_count, True


def parse_datasets(
    datasets: list,
    connector: str,
    supports_incremental: bool,
    seen: set[str],
) -> tuple[Dataset, ...]:
    parsed = []
    for dataset in datasets:
        name = str(dataset.get("name"))
        if name in seen:
            raise InstanceProfileError(f"the profile declares the dataset '{name}' twice")
        seen.add(name)

        primary_key = dataset.get("primary_key") or []
        if not isinstance(primary_key, list) or not primary_key:
            raise InstanceProfileError(f"the dataset '{name}' must declare a primary key")

        load_mode = dataset.get("load_mode")
        if load_mode not in LOAD_MODES:
            raise InstanceProfileError(f"the dataset '{name}' declares the unknown load mode '{load_mode}'")
        if load_mode == "incremental" and not supports_incremental:
            raise InstanceProfileError(f"the connector '{connector}' cannot read the dataset '{name}' incrementally")

        watermark = dataset.get("watermark_column")
        if load_mode == "incremental" and not watermark:
            raise InstanceProfileError(f"the incremental dataset '{name}' must declare a watermark column")
        if load_mode == "full" and watermark:
            raise InstanceProfileError(f"the full dataset '{name}' must not declare a watermark column")

        parsed.append(
            Dataset(
                name=name,
                primary_key=tuple(str(key) for key in primary_key),
                load_mode=load_mode,
                watermark_column=str(watermark) if watermark else None,
            )
        )
    return tuple(parsed)


def parse_credentials(credentials: list) -> tuple[CredentialRef, ...]:
    parsed = []
    for credential in credentials:
        name = str(credential.get("name"))
        inline = [field for field in SECRET_FIELDS if credential.get(field)]
        if inline or not credential.get("reference"):
            raise InstanceProfileError(f"the credential '{name}' must reference a secret store, never carry a value")
        parsed.append(
            CredentialRef(
                name=name,
                store=str(credential.get("store", "")),
                reference=str(credential["reference"]),
            )
        )
    return tuple(parsed)


def workspace_name(profile: InstanceProfile, environment: str) -> str:
    if environment not in profile.environments:
        raise InstanceProfileError(f"the environment '{environment}' is not declared by the profile")
    return f"ws_{profile.project_slug}_{environment}"


def feature_workspace_name(profile: InstanceProfile, work_item_id: int) -> str:
    if work_item_id < 1:
        raise InstanceProfileError("the work item identifier must be positive")
    return f"ws_{profile.project_slug}_feature_wi{work_item_id}"
