"""Safe failure reporting for agent sessions."""

import json
import shutil


QUOTA_EXHAUSTED = "agent_quota_exhausted"
AUTHENTICATION_FAILED = "agent_authentication_failed"
SESSION_ERROR = "session_error"

# A blocked runtime is not a defect of the work item: the same ticket must stay available.
RETRYABLE_FAILURE_CLASSES = frozenset({QUOTA_EXHAUSTED, AUTHENTICATION_FAILED})


def resolve_agent_command(command: str) -> str:
    """Resolve platform executable suffixes while keeping configuration portable."""
    return shutil.which(command) or command


def classify_session_failure(returncode: int, stdout: str) -> str:
    """Name the cause of a failed session so a blocked runtime is not read as a bad ticket."""
    try:
        payload = json.loads(stdout) if stdout.strip() else {}
    except (TypeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    result = str(payload.get("result", "")).lower()
    if payload.get("api_error_status") == 429 or "session limit" in result or "rate limit" in result:
        return QUOTA_EXHAUSTED
    if payload.get("api_error_status") in (401, 403) or "authenticate" in result or "oauth" in result:
        return AUTHENTICATION_FAILED
    return SESSION_ERROR


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
