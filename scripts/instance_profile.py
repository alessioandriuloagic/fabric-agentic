"""Portable instance profile: one client or project deployment, without secrets."""

import json
import re
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_SCHEMA_VERSIONS = ("1.0",)
SUPPORTED_TRACKERS = ("github_issues", "azure_devops")
SUPPORTED_CONNECTORS = ("crm_dataverse", "file")
LOAD_MODES = ("full", "incremental")

SLUG = re.compile(r"^[a-z][a-z0-9_]*$")
SECRET_FIELDS = ("value", "secret", "password", "token", "client_secret")


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
    datasets: tuple[Dataset, ...]


@dataclass(frozen=True)
class CredentialRef:
    name: str
    store: str
    reference: str


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
    )


def parse_sources(sources: list) -> tuple[Source, ...]:
    parsed = []
    seen_datasets: set[str] = set()
    for source in sources:
        connector = source.get("connector")
        if connector not in SUPPORTED_CONNECTORS:
            raise InstanceProfileError(f"unknown connector '{connector}'")
        if not source.get("connection_ref"):
            raise InstanceProfileError(f"the source '{source.get('name')}' must reference a connection")
        parsed.append(
            Source(
                name=str(source.get("name")),
                connector=connector,
                connection_ref=str(source["connection_ref"]),
                datasets=parse_datasets(source.get("datasets") or [], seen_datasets),
            )
        )
    return tuple(parsed)


def parse_datasets(datasets: list, seen: set[str]) -> tuple[Dataset, ...]:
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
