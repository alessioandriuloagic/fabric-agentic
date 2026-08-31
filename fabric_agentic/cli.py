"""Command line entry point: validate a profile, render it, and check what is provisioned."""

import argparse
from pathlib import Path

from fabric_agentic import __version__
from fabric_agentic.console import serve
from fabric_agentic.control import AgentStatus, agent_home, describe_all
from fabric_agentic.instance_profile import InstanceProfile, InstanceProfileError, load_profile
from fabric_agentic.render import render


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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    home = args.home or agent_home()

    if args.command == "console":
        serve(args.port, home)
        return 0

    if args.command == "validate":
        return _validate(args.config)

    if args.command == "render":
        return _render(args.config, args.output)

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


def _doctor(home: Path, config_path: Path | None) -> int:
    statuses = describe_all(home)
    print(render_text(statuses, home))

    profile_ready = _validate(config_path) == 0 if config_path is not None else True
    return 0 if profile_ready and all(status.ready for status in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
