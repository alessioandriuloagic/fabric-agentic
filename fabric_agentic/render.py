"""Deterministic deployment plan derived from an instance profile."""

import json
from pathlib import Path

from fabric_agentic.connectors import get_connector
from fabric_agentic.instance_profile import (
    InstanceProfile,
    feature_workspace_name,
    workspace_name,
)


PLAN_NAME = "plan.json"
SUMMARY_NAME = "README.md"
FEATURE_PLACEHOLDER = 1


def build_plan(profile: InstanceProfile) -> dict:
    return {
        "schema_version": profile.schema_version,
        "project": {"slug": profile.project_slug, "display_name": profile.display_name},
        "tracker": {"type": profile.tracker_type},
        "workspaces": [
            {"environment": environment, "name": workspace_name(profile, environment)}
            for environment in profile.environments
        ],
        "feature_workspace_pattern": feature_workspace_name(profile, FEATURE_PLACEHOLDER).replace(
            f"wi{FEATURE_PLACEHOLDER}", "wi<work-item>"
        ),
        "sources": [_source_plan(source) for source in profile.sources],
        "credentials": [
            {"name": credential.name, "store": credential.store, "reference": credential.reference}
            for credential in profile.credentials
        ],
    }


def render(profile: InstanceProfile, output_directory: Path) -> tuple[Path, ...]:
    plan = build_plan(profile)
    output_directory.mkdir(parents=True, exist_ok=True)

    plan_path = output_directory / PLAN_NAME
    summary_path = output_directory / SUMMARY_NAME
    _write(plan_path, json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    _write(summary_path, render_summary(plan))
    return (plan_path, summary_path)


def render_summary(plan: dict) -> str:
    project = plan["project"]
    lines = [
        f"# {project['display_name']}",
        "",
        "Generato da `fabric-agentic render`. Non modificare a mano: rigenerare dal profilo.",
        "",
        f"- Slug progetto: `{project['slug']}`",
        f"- Tracker: `{plan['tracker']['type']}`",
        f"- Workspace di feature: `{plan['feature_workspace_pattern']}`",
        "",
        "## Workspace",
        "",
        "| Ambiente | Workspace |",
        "|---|---|",
    ]
    lines += [f"| `{entry['environment']}` | `{entry['name']}` |" for entry in plan["workspaces"]]

    for source in plan["sources"]:
        capabilities = source["capabilities"]
        lines += [
            "",
            f"## Sorgente `{source['name']}`",
            "",
            f"- Connector: `{source['connector']}`",
            f"- Adapter operativo: {'disponibile' if source['adapter_available'] else 'da implementare'}",
            f"- Connessione: `{source['connection_ref']}`",
            f"- Lettura incrementale: {'sì' if capabilities['supports_incremental'] else 'no'}",
            f"- Conteggio alla sorgente: {'sì' if capabilities['supports_source_count'] else 'no'}",
            "",
            "| Dataset | Chiave primaria | Carico | Watermark |",
            "|---|---|---|---|",
        ]
        for dataset in source["datasets"]:
            watermark = f"`{dataset['watermark_column']}`" if dataset["watermark_column"] else "—"
            key = ", ".join(f"`{column}`" for column in dataset["primary_key"])
            lines.append(f"| `{dataset['name']}` | {key} | `{dataset['load_mode']}` | {watermark} |")

    if plan["credentials"]:
        lines += [
            "",
            "## Credenziali",
            "",
            "Solo riferimenti a un secret store: nessun valore è generato qui.",
            "",
            "| Nome | Store | Riferimento |",
            "|---|---|---|",
        ]
        lines += [
            f"| `{credential['name']}` | `{credential['store']}` | `{credential['reference']}` |"
            for credential in plan["credentials"]
        ]

    return "\n".join(lines) + "\n"


def _source_plan(source) -> dict:
    connection_fields = []
    if source.adapter_available:
        connection_fields = list(get_connector(source.connector).connection_fields)
    return {
        "name": source.name,
        "connector": source.connector,
        "connection_ref": source.connection_ref,
        "adapter_available": source.adapter_available,
        "capabilities": {
            "supports_incremental": source.supports_incremental,
            "supports_source_count": source.supports_source_count,
            "connection_fields": connection_fields,
        },
        "datasets": [
            {
                "name": dataset.name,
                "primary_key": list(dataset.primary_key),
                "load_mode": dataset.load_mode,
                "watermark_column": dataset.watermark_column,
            }
            for dataset in source.datasets
        ],
    }


def _write(path: Path, content: str) -> None:
    """Fixed newline so the same profile renders byte-for-byte on Windows and POSIX."""
    path.write_text(content, encoding="utf-8", newline="\n")
