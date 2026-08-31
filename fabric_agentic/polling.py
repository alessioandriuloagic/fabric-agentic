"""Bounded polling loop shared by the dispatchers."""

import time
from dataclasses import dataclass
from typing import Callable


DEFAULT_MAX_CONSECUTIVE_FAILURES = 3


class PollingStopped(Exception):
    """Raised when the loop gives up instead of retrying an operation that keeps failing."""


@dataclass(frozen=True)
class PollingReport:
    cycles: int
    failures: int


def run_polling(
    cycle: Callable[[], list],
    poll_seconds: int,
    errors: tuple[type[Exception], ...],
    cycles: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
    on_cycle: Callable[[list], None] = lambda tasks: None,
    on_error: Callable[[Exception], None] = lambda error: None,
    max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES,
) -> PollingReport:
    completed = 0
    failures = 0
    consecutive = 0

    while cycles is None or completed < cycles:
        try:
            on_cycle(cycle())
            consecutive = 0
        except errors as error:
            failures += 1
            consecutive += 1
            on_error(error)
            # A failed cycle never advances the anti-loop state, so retrying without a bound would
            # relaunch the same expensive session at every interval.
            if consecutive >= max_consecutive_failures:
                raise PollingStopped(f"stopped after {consecutive} consecutive failed cycles") from None

        completed += 1
        if cycles is None or completed < cycles:
            sleep(poll_seconds)

    return PollingReport(cycles=completed, failures=failures)
