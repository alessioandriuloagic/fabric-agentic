"""Local readiness of the agent chain: what is provisioned, what is missing, how it starts."""

import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fabric_agentic.config_paths import expand_path


AGENTS = ("issue", "dev", "review")
HOME_VARIABLE = "FABRIC_AGENTIC_HOME"
CONFIG_NAME = "dispatcher-config.json"
KEY_NAME = "github-app-private-key.pem"
TRACKERS = ("github_issues", "azure_devops")

ROLES = {
    "issue": "Trasforma una richiesta in un pacchetto di lavoro da approvare",
    "dev": "Implementa un ticket approvato e apre la pull request",
    "review": "Rivede una pull request ed emette un voto",
}
# Only the dev dispatcher owns a polling loop; the other two run one cycle per invocation.
CONTINUOUS = {"dev"}
# Mirrors what each dispatcher's own load_config reads, so a green check cannot precede a red start.
REQUIRED_SECTIONS = {
    "issue": ("github", "agent"),
    "dev": ("github", "agent", "azure_devops"),
    "review": ("github", "agent"),
}


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class AgentStatus:
    agent: str
    role: str
    directory: Path
    checks: tuple[Check, ...]
    activity: str
    repository: str
    start_command: str
    continuous: bool

    @property
    def ready(self) -> bool:
        return all(check.ok for check in self.checks)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(check.name for check in self.checks if not check.ok)


def agent_home() -> Path:
    configured = os.environ.get(HOME_VARIABLE)
    return expand_path(configured) if configured else Path.home() / ".fabric-agentic"


def describe_all(home: Path | None = None) -> tuple[AgentStatus, ...]:
    root = home or agent_home()
    return tuple(describe_agent(agent, root) for agent in AGENTS)


def describe_agent(agent: str, home: Path | None = None) -> AgentStatus:
    if agent not in AGENTS:
        raise ValueError(f"unknown agent '{agent}'")

    directory = (home or agent_home()) / f"{agent}-agent"
    config_path = directory / CONFIG_NAME
    config = _read_config(config_path)

    checks = [
        _check_configuration(agent, config_path, config),
        _check_identity(config),
        _check_private_key(directory, config),
        _check_clone(config),
    ]
    if agent == "dev":
        checks.append(_check_tracker(config))

    return AgentStatus(
        agent=agent,
        role=ROLES[agent],
        directory=directory,
        checks=tuple(checks),
        activity=_last_cycle(directory),
        repository=_repository(config),
        start_command=_start_command(agent, directory),
        continuous=agent in CONTINUOUS,
    )


def _read_config(config_path: Path) -> dict | None:
    try:
        document = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def _check_configuration(agent: str, config_path: Path, config: dict | None) -> Check:
    if config is None:
        return Check("configurazione", False, f"manca o non è JSON valido: {config_path.name}")
    missing = [section for section in REQUIRED_SECTIONS[agent] if not config.get(section)]
    if missing:
        return Check("configurazione", False, f"manca la sezione '{missing[0]}'")
    return Check("configurazione", True, config_path.name)


def _check_identity(config: dict | None) -> Check:
    github = (config or {}).get("github") or {}
    try:
        app_id = int(github.get("app_id", 0))
        installation_id = int(github.get("installation_id", 0))
    except (TypeError, ValueError):
        return Check("identità", False, "app_id o installation_id non numerici")
    if app_id < 1 or installation_id < 1:
        return Check("identità", False, "GitHub App non provisionata")
    return Check("identità", True, f"App {app_id}, installazione {installation_id}")


def _check_private_key(directory: Path, config: dict | None) -> Check:
    declared = ((config or {}).get("github") or {}).get("private_key_path")
    key_path = expand_path(str(declared)) if declared else directory / KEY_NAME
    if not key_path.is_file():
        return Check("chiave privata", False, "assente nel percorso dichiarato")
    if os.name != "nt" and stat.S_IMODE(key_path.stat().st_mode) & 0o077:
        return Check("chiave privata", False, "leggibile oltre il proprietario")
    return Check("chiave privata", True, "presente e riservata al proprietario")


def _check_clone(config: dict | None) -> Check:
    declared = ((config or {}).get("agent") or {}).get("repository_path")
    if not declared:
        return Check("clone dedicato", False, "non dichiarato")
    clone = expand_path(str(declared))
    if not (clone / ".git").exists():
        return Check("clone dedicato", False, "il percorso dichiarato non è un clone Git")
    return Check("clone dedicato", True, str(clone))


def _check_tracker(config: dict | None) -> Check:
    """An undeclared tracker silently falls back to Azure DevOps, contradicting a GitHub configuration."""
    declared = ((config or {}).get("dispatcher") or {}).get("tracker_type")
    if not declared:
        return Check("tracker", False, "non dichiarato: il dispatcher ripiegherebbe su azure_devops")
    if declared not in TRACKERS:
        return Check("tracker", False, f"tracker sconosciuto '{declared}'")
    return Check("tracker", True, declared)


def _last_cycle(directory: Path) -> str:
    """Observed history, never a readiness gate: a freshly configured agent has simply not run yet."""
    state_path = directory / "state.json"
    if not state_path.is_file():
        return "nessun ciclo registrato"
    moment = datetime.fromtimestamp(state_path.stat().st_mtime, tz=timezone.utc)
    return f"ultimo ciclo {moment.strftime('%Y-%m-%d %H:%M UTC')}"


def _repository(config: dict | None) -> str:
    github = (config or {}).get("github") or {}
    owner = github.get("owner")
    repository = github.get("repository")
    return f"{owner}/{repository}" if owner and repository else "non dichiarato"


def _start_command(agent: str, directory: Path) -> str:
    arguments = [
        f"--config {directory / CONFIG_NAME}",
        f"--state {directory / 'state.json'}",
        f"--tasks {directory / 'tasks'}",
    ]
    if agent in CONTINUOUS:
        arguments += [f"--log {directory / 'dispatcher.log'}", "--poll"]
    else:
        arguments.append("--once")
    return f"python -m scripts.{agent}_dispatcher " + " ".join(arguments)
