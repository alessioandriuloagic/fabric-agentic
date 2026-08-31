"""Localhost credential broker shared by the agent dispatchers."""

import json
import os
import shutil
import socketserver
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class CredentialBrokerHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            request = json.loads(self.rfile.readline().decode("utf-8"))
            if request.get("kind") not in {"git", "gh"}:
                raise ValueError
            self.wfile.write(json.dumps({"token": self.server.token}).encode("utf-8"))
        except (AttributeError, json.JSONDecodeError, ValueError):
            self.wfile.write(b'{"error":"invalid credential request"}')


class CredentialBroker(socketserver.ThreadingTCPServer):
    allow_reuse_address = False

    def __init__(self, token: str):
        super().__init__(("127.0.0.1", 0), CredentialBrokerHandler)
        self.token = token


def write_executable(directory: Path, name: str, command: str) -> Path:
    """Write a PATH shim that works both as a Windows .cmd and as a POSIX executable."""
    if os.name == "nt":
        script = directory / f"{name}.cmd"
        script.write_text(f"@echo off\n{command} %*\n", encoding="utf-8")
        return script
    script = directory / name
    script.write_text(f'#!/bin/sh\n{command} "$@"\n', encoding="utf-8", newline="\n")
    script.chmod(0o755)
    return script


@contextmanager
def credential_broker_environment(token: str) -> Iterator[dict[str, str]]:
    broker = CredentialBroker(token)
    broker_thread = threading.Thread(target=broker.serve_forever, daemon=True)
    broker_thread.start()
    with tempfile.TemporaryDirectory(prefix="fabric-agentic-credentials-") as directory:
        helper_script = Path(__file__).with_name("credential_helper.py")
        real_gh = shutil.which("gh") or "gh"
        helper = write_executable(
            Path(directory), "credential-helper", f'"{sys.executable}" "{helper_script}" git'
        )
        write_executable(
            Path(directory), "gh", f'"{sys.executable}" "{helper_script}" gh "{real_gh}"'
        )
        hooks_directory = Path(directory) / "git-hooks"
        hooks_directory.mkdir()
        hook = hooks_directory / "pre-push"
        hook.write_text(
            "#!/bin/sh\n"
            "while read local_ref local_oid remote_ref remote_oid; do\n"
            "  case \"$remote_ref\" in\n"
            "    refs/heads/main) exit 1 ;;\n"
            "  esac\n"
            "done\n"
            "exit 0\n",
            encoding="utf-8",
            newline="\n",
        )
        # Git silently skips a hook that is not executable, which would disable the main guard.
        hook.chmod(0o755)
        environment = os.environ.copy()
        environment.pop("GH_TOKEN", None)
        environment.pop("GITHUB_TOKEN", None)
        environment["GIT_ASKPASS"] = str(helper)
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["FABRIC_AGENT_CREDENTIAL_BROKER"] = f"127.0.0.1:{broker.server_address[1]}"
        environment["GIT_CONFIG_COUNT"] = "2"
        environment["GIT_CONFIG_KEY_0"] = "core.hooksPath"
        environment["GIT_CONFIG_VALUE_0"] = str(hooks_directory)
        # Neutralise any ambient credential manager so the session can only use the brokered token.
        environment["GIT_CONFIG_KEY_1"] = "credential.helper"
        environment["GIT_CONFIG_VALUE_1"] = ""
        environment["PATH"] = f"{directory}{os.pathsep}{environment.get('PATH', '')}"
        try:
            yield environment
        finally:
            broker.shutdown()
            broker.server_close()
            broker_thread.join(timeout=2)
