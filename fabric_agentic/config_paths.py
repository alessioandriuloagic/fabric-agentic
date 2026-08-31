"""Path expansion shared by the agent dispatchers."""

import os
import re
from pathlib import Path


WINDOWS_VARIABLE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)%")
HOME_VARIABLES = frozenset({"USERPROFILE", "HOME"})


def expand_path(value: str) -> Path:
    """Accept both %VAR% and $VAR so one configuration file works on Windows and POSIX."""
    expanded = WINDOWS_VARIABLE.sub(_expand_windows_variable, value)
    return Path(os.path.expandvars(expanded)).expanduser()


def _expand_windows_variable(match: re.Match[str]) -> str:
    name = match.group(1)
    value = os.environ.get(name)
    if value is not None:
        return value
    return str(Path.home()) if name.upper() in HOME_VARIABLES else match.group(0)
