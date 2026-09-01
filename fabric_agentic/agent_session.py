"""Safe failure reporting for agent sessions."""

import json
import shutil


def resolve_agent_command(command: str) -> str:
    """Resolve platform executable suffixes while keeping configuration portable."""
    return shutil.which(command) or command


def session_failure_reason(returncode: int, stdout: str) -> str:
    """Summarise a failed session using structured status only, never the transcript."""
    details = [f"exit={returncode}"]
    try:
        payload = json.loads(stdout) if stdout.strip() else {}
    except (TypeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    for field in ("subtype", "stop_reason", "terminal_reason", "api_error_status", "session_id", "num_turns"):
        value = payload.get(field)
        if value not in (None, ""):
            details.append(f"{field}={value}")
    return ", ".join(details)
