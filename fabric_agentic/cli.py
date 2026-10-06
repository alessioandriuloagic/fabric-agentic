"""Command line entry point: validate a profile, render it, and check what is provisioned."""

import argparse
import json
import sys
from pathlib import Path

from fabric_agentic import __version__
from fabric_agentic.bootstrap import InitError, init as init_starter
from fabric_agentic.console import serve
from fabric_agentic.control import AgentStatus, agent_home, describe_all
from fabric_agentic.instance_profile import InstanceProfile, InstanceProfileError, load_profile
from fabric_agentic.render import render
from fabric_agentic.user_session import UserSession, UserSessionError


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="fabric-agentic")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--home", type=Path, help="cartella degli agenti, per default ~/.fabric-agentic")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="verifica il profilo di istanza")
    validate.add_argument("--config", type=Path, required=True)

    render_command = commands.add_parser("render", help="genera il piano di deployment dal profilo")
    render_command.add_argument("--config", type=Path, required=True)
    render_command.add_argument("--output", type=Path, required=True)

    doctor = commands.add_parser("doctor", help="verifica cosa è pronto e cosa manca")
    doctor.add_argument("--config", type=Path, help="verifica anche il profilo di istanza")

    console = commands.add_parser("console", help="apre la console locale in sola lettura")
    console.add_argument("--port", type=int, default=8765)

    init_command = commands.add_parser("init", help="crea un profilo di istanza e la checklist di bootstrap")
    init_command.add_argument("--directory", type=Path, required=True)
    init_command.add_argument("--project-slug", help="per default derivato dal nome della cartella")
    init_command.add_argument("--display-name", help="per default uguale allo slug")
    init_command.add_argument("--force", action="store_true", help="sovrascrive i file già presenti")
    init_command.add_argument("--tenant-id", help="tenant cliente per il percorso utente assistito")
    init_command.add_argument("--workspace-id", help="workspace esistente per il preflight assistito")
    init_command.add_argument("--account", help="utenza nominale o di servizio autorizzata")

    session = commands.add_parser("session", help="login utente assistito e verifica Fabric senza SP")
    session.add_argument("action", choices=("login", "status", "logout"))
    session.add_argument("--config", type=Path, required=True)

    return parser.parse_args(argv)


def render_profile(profile: InstanceProfile) -> str:
    datasets = [dataset for source in profile.sources for dataset in source.datasets]
    return "\n".join(
        [
            f"profilo valido: {profile.display_name} ({profile.project_slug})",
            f"   tracker: {profile.tracker_type}",
            f"   ambienti: {', '.join(profile.environments)}",
            f"   sorgenti: {len(profile.sources)}, dataset: {len(datasets)}",
        ]
    )


def render_text(statuses: tuple[AgentStatus, ...], home: Path) -> str:
    lines = [f"home: {home}", ""]
    for status in statuses:
        lines.append(f"{'OK ' if status.ready else 'DA CONFIGURARE'} {status.agent} — {status.role}")
        for check in status.checks:
            lines.append(f"   {'✓' if check.ok else '✗'} {check.name}: {check.detail}")
        lines.append(f"   attività: {status.activity}")
        lines.append(f"   avvio: {status.start_command}")
        lines.append("")
    return "\n".join(lines)


def use_unicode_output() -> None:
    """The default Windows console codepage cannot encode the status marks or accented Italian."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    use_unicode_output()
    home = args.home or agent_home()

    if args.command == "console":
        serve(args.port, home)
        return 0

    if args.command == "validate":
        return _validate(args.config)

    if args.command == "render":
        return _render(args.config, args.output)

    if args.command == "init":
        execution = None
        if any(value is not None for value in (args.tenant_id, args.workspace_id, args.account)):
            execution = {"mode": "delegated_assisted", "tenant_id": args.tenant_id,
                         "workspace_id": args.workspace_id, "account": args.account}
        return _init(args.directory, args.project_slug, args.display_name, args.force, execution)

    if args.command == "session":
        return _session(home, args.config, args.action)

    return _doctor(home, args.config)


def _validate(config_path: Path) -> int:
    try:
        profile = load_profile(config_path)
    except InstanceProfileError as error:
        print(f"profilo non valido: {error}")
        return 1
    print(render_profile(profile))
    return 0


def _render(config_path: Path, output_directory: Path) -> int:
    try:
        profile = load_profile(config_path)
    except InstanceProfileError as error:
        print(f"profilo non valido: {error}")
        return 1
    for path in render(profile, output_directory):
        print(f"generato: {path}")
    return 0


def _init(
    directory: Path, project_slug: str | None, display_name: str | None, force: bool,
    execution: dict | None = None,
) -> int:
    try:
        result = init_starter(directory, project_slug, display_name, force, execution)
    except InitError as error:
        print(f"init non riuscito: {error}")
        return 1
    for path in result.written:
        print(f"generato: {path}")
    for path in result.skipped:
        print(f"già presente, non sovrascritto (usa --force per rigenerare): {path}")
    return 0


def _doctor(home: Path, config_path: Path | None) -> int:
    statuses = describe_all(home)
    print(render_text(statuses, home))

    profile_ready = _validate(config_path) == 0 if config_path is not None else True
    return 0 if profile_ready and all(status.ready for status in statuses) else 1


def _session(home: Path, config_path: Path, action: str) -> int:
    try:
        execution = load_profile(config_path).execution
        if execution is None:
            raise UserSessionError("execution_not_configured")
        session = UserSession(execution.tenant_id, execution.workspace_id, execution.account, home)
        if action == "logout":
            report = session.logout()
            report["outcome"] = "logged_out"
        else:
            if action == "login":
                session.login()
            report = session.preflight()
            report["outcome"] = "success"
    except InstanceProfileError:
        print(json.dumps({"outcome": "blocked", "code": "invalid_profile"}))
        return 1
    except UserSessionError as error:
        report = {"outcome": "blocked", "code": str(error)}
        if str(error) == "login_required":
            report["next_action"] = "session login --config <profile>"
        print(json.dumps(report))
        return 1
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
