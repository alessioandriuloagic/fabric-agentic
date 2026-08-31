"""Command line entry point: check readiness and open the local console."""

import argparse
from pathlib import Path

from fabric_agentic import __version__
from fabric_agentic.console import serve
from fabric_agentic.control import AgentStatus, agent_home, describe_all


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="fabric-agentic")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--home", type=Path, help="cartella degli agenti, per default ~/.fabric-agentic")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor", help="verifica cosa è pronto e cosa manca")
    console = commands.add_parser("console", help="apre la console locale in sola lettura")
    console.add_argument("--port", type=int, default=8765)

    return parser.parse_args(argv)


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

    statuses = describe_all(home)
    print(render_text(statuses, home))
    return 0 if all(status.ready for status in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
