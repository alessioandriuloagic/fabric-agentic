"""Durable ledger of dispatch attempts, with an atomic claim and an expiring lease.

Two dispatchers must never run the same work item at the same time, and a dispatcher that
crashes must not keep it forever: the claim is atomic on the file system, and the lease
expires so the next cycle recovers the work instead of leaving it stuck. Every attempt
carries its own evidence — identifier, work item, source revision, state, lease and retry
count — and nothing else: no token, no credential, no work item content.
"""

import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator

RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
RELEASED = "released"
EXPIRED = "expired"

# A released or expired attempt returns the work item to the queue; a succeeded or failed one
# does not, because the dispatcher never relaunches a session blindly.
CLOSING_STATES = frozenset({SUCCEEDED, FAILED, RELEASED})
BLOCKING_STATES = frozenset({SUCCEEDED, FAILED})

LEDGER_VERSION = 1
DEFAULT_LEASE_SECONDS = 900
LOCK_TIMEOUT_SECONDS = 10
LOCK_RETRY_SECONDS = 0.05
UNKNOWN_REVISION = "unknown"


class AttemptLedgerError(Exception):
    """Raised without including credentials, ledger content or work item content."""


@dataclass(frozen=True)
class Attempt:
    """One dispatch attempt: what was tried, from which revision, by whom, and until when."""

    attempt_id: str
    work_item_id: int | str
    source_revision: str
    state: str
    lease_owner: str
    lease_expires_at: str
    retry_count: int
    started_at: str
    updated_at: str


def _now() -> datetime:
    return datetime.now(UTC)


def _stamp(moment: datetime) -> str:
    return moment.isoformat()


def _parse(moment: str) -> datetime:
    try:
        return datetime.fromisoformat(moment)
    except (TypeError, ValueError) as error:
        raise AttemptLedgerError("the attempt ledger is invalid") from error


def _blocks(attempt: Attempt, now: datetime) -> bool:
    """Report whether an attempt keeps its work item out of the queue."""
    if attempt.state in BLOCKING_STATES:
        return True
    return attempt.state == RUNNING and now < _parse(attempt.lease_expires_at)


class AttemptLedger:
    """A single JSON file, outside the repository, holding every attempt of one agent."""

    def __init__(self, path: Path, lease_seconds: int = DEFAULT_LEASE_SECONDS, owner: str | None = None) -> None:
        self.path = Path(path)
        self.lease_seconds = int(lease_seconds)
        # The owner names the process holding the lease; it is an identifier, never an identity.
        self.owner = owner or f"pid-{os.getpid()}-{uuid.uuid4().hex[:8]}"

    def attempts(self) -> tuple[Attempt, ...]:
        return tuple(self._read())

    def claimed_work_items(self) -> set[int | str]:
        """Work items that must not be dispatched now, either held or already concluded."""
        now = _now()
        return {attempt.work_item_id for attempt in self._read() if _blocks(attempt, now)}

    def claim(self, work_item_id: int | str, source_revision: str) -> Attempt | None:
        """Take the work item under a fresh lease, or return None if someone else holds it."""
        with self._lock():
            attempts = self._read()
            now = _now()
            history = [attempt for attempt in attempts if attempt.work_item_id == work_item_id]
            if any(_blocks(attempt, now) for attempt in history):
                return None
            # Whatever is still marked running has outlived its lease: the dispatcher that held it
            # crashed or was killed, and the attempt is closed as expired before the retry starts.
            recovered = [
                replace(attempt, state=EXPIRED, updated_at=_stamp(now))
                if attempt.work_item_id == work_item_id and attempt.state == RUNNING
                else attempt
                for attempt in attempts
            ]
            claimed = Attempt(
                attempt_id=str(uuid.uuid4()),
                work_item_id=work_item_id,
                source_revision=source_revision or UNKNOWN_REVISION,
                state=RUNNING,
                lease_owner=self.owner,
                lease_expires_at=_stamp(now + timedelta(seconds=self.lease_seconds)),
                retry_count=len(history),
                started_at=_stamp(now),
                updated_at=_stamp(now),
            )
            self._write([*recovered, claimed])
            return claimed

    def renew(self, attempt_id: str) -> Attempt:
        """Extend the lease of a running attempt, so a long session is never stolen mid-flight."""
        with self._lock():
            attempts = self._read()
            now = _now()
            held = self._held(attempts, attempt_id)
            renewed = replace(
                held,
                lease_expires_at=_stamp(now + timedelta(seconds=self.lease_seconds)),
                updated_at=_stamp(now),
            )
            self._write([renewed if attempt.attempt_id == attempt_id else attempt for attempt in attempts])
            return renewed

    def close(self, attempt_id: str, state: str) -> Attempt:
        """Record the outcome of an attempt this dispatcher still holds."""
        if state not in CLOSING_STATES:
            raise AttemptLedgerError("that is not a terminal attempt state")
        with self._lock():
            attempts = self._read()
            held = self._held(attempts, attempt_id)
            closed = replace(held, state=state, updated_at=_stamp(_now()))
            self._write([closed if attempt.attempt_id == attempt_id else attempt for attempt in attempts])
            return closed

    def _held(self, attempts: Iterable[Attempt], attempt_id: str) -> Attempt:
        """Refuse to touch an attempt this dispatcher no longer holds: the lease may have moved on."""
        for attempt in attempts:
            if attempt.attempt_id != attempt_id:
                continue
            if attempt.state != RUNNING or attempt.lease_owner != self.owner:
                raise AttemptLedgerError("the attempt lease is no longer held")
            return attempt
        raise AttemptLedgerError("the attempt is not in the ledger")

    @contextmanager
    def _lock(self) -> Iterator[None]:
        """Serialise read-modify-write across processes: O_EXCL is atomic on Windows and POSIX."""
        lock_path = self.path.with_suffix(".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError as error:
                if time.monotonic() >= deadline:
                    raise AttemptLedgerError("the attempt ledger is locked by another dispatcher") from error
                time.sleep(LOCK_RETRY_SECONDS)
        try:
            os.close(descriptor)
            yield
        finally:
            lock_path.unlink(missing_ok=True)

    def _read(self) -> list[Attempt]:
        if not self.path.exists():
            return []
        try:
            document = json.loads(self.path.read_text(encoding="utf-8-sig"))
            return [Attempt(**record) for record in document["attempts"]]
        except (OSError, TypeError, ValueError, KeyError) as error:
            raise AttemptLedgerError("the attempt ledger is invalid") from error

    def _write(self, attempts: Iterable[Attempt]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = {"version": LEDGER_VERSION, "attempts": [asdict(attempt) for attempt in attempts]}
        temporary_path = self.path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        temporary_path.replace(self.path)


@contextmanager
def lease_heartbeat(ledger: AttemptLedger, attempt_id: str, interval_seconds: float) -> Iterator[None]:
    """Renew the lease while a session runs, so the lease can stay short enough to recover a crash.

    Without it the lease would have to outlast the longest possible session, and a crashed
    dispatcher would keep the work item for that whole duration.
    """
    stopped = threading.Event()

    def renew_until_stopped() -> None:
        while not stopped.wait(interval_seconds):
            try:
                ledger.renew(attempt_id)
            except AttemptLedgerError:
                return

    worker = threading.Thread(target=renew_until_stopped, daemon=True)
    worker.start()
    try:
        yield
    finally:
        stopped.set()
        worker.join(timeout=LOCK_TIMEOUT_SECONDS)
