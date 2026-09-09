import json
import subprocess
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fabric_agentic.attempt_ledger import (
    EXPIRED,
    FAILED,
    RELEASED,
    RUNNING,
    SUCCEEDED,
    AttemptLedger,
    AttemptLedgerError,
    lease_heartbeat,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# One dispatcher per process, all claiming the same work item: exactly one may win.
CONCURRENT_CLAIM = """
import json, sys
from fabric_agentic.attempt_ledger import AttemptLedger

attempt = AttemptLedger(sys.argv[1]).claim(183, "0f1e2d3")
print(json.dumps({"claimed": attempt is not None}))
"""


class AttemptLedgerTests(unittest.TestCase):
    def test_a_claim_records_the_evidence_of_the_attempt(self) -> None:
        with TemporaryDirectory() as directory:
            ledger = AttemptLedger(Path(directory) / "attempts.json")

            attempt = ledger.claim(183, "0f1e2d3")

        self.assertEqual(attempt.work_item_id, 183)
        self.assertEqual(attempt.source_revision, "0f1e2d3")
        self.assertEqual(attempt.state, RUNNING)
        self.assertEqual(attempt.retry_count, 0)
        self.assertTrue(attempt.attempt_id)
        self.assertTrue(attempt.lease_expires_at)

    def test_a_second_dispatcher_cannot_claim_a_work_item_under_a_live_lease(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "attempts.json"
            first = AttemptLedger(path).claim(183, "0f1e2d3")

            second = AttemptLedger(path).claim(183, "0f1e2d3")

        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_concurrent_dispatchers_never_claim_the_same_work_item(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "attempts.json"
            processes = [
                subprocess.Popen(
                    [sys.executable, "-c", CONCURRENT_CLAIM, str(path)],
                    cwd=REPOSITORY_ROOT,
                    stdout=subprocess.PIPE,
                    text=True,
                )
                for _ in range(4)
            ]
            claims = [json.loads(process.communicate()[0])["claimed"] for process in processes]
            attempts = AttemptLedger(path).attempts()

        self.assertEqual(claims.count(True), 1)
        self.assertEqual(len(attempts), 1)

    def test_an_expired_lease_is_recovered_with_an_incremented_retry_count(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "attempts.json"
            crashed = AttemptLedger(path, lease_seconds=0).claim(183, "0f1e2d3")

            recovered = AttemptLedger(path).claim(183, "9a8b7c6")
            states = {attempt.attempt_id: attempt.state for attempt in AttemptLedger(path).attempts()}

        self.assertEqual(recovered.retry_count, 1)
        self.assertEqual(recovered.source_revision, "9a8b7c6")
        self.assertEqual(states[crashed.attempt_id], EXPIRED)
        self.assertEqual(states[recovered.attempt_id], RUNNING)

    def test_a_released_attempt_returns_the_work_item_to_the_queue(self) -> None:
        with TemporaryDirectory() as directory:
            ledger = AttemptLedger(Path(directory) / "attempts.json")
            blocked = ledger.claim(183, "0f1e2d3")
            ledger.close(blocked.attempt_id, RELEASED)

            retried = ledger.claim(183, "0f1e2d3")

            self.assertEqual(retried.retry_count, 1)
            self.assertEqual(ledger.claimed_work_items(), {183})

    def test_a_concluded_attempt_is_never_claimed_again(self) -> None:
        with TemporaryDirectory() as directory:
            ledger = AttemptLedger(Path(directory) / "attempts.json")
            delivered = ledger.claim(183, "0f1e2d3")
            ledger.close(delivered.attempt_id, SUCCEEDED)
            defective = ledger.claim(184, "0f1e2d3")
            ledger.close(defective.attempt_id, FAILED)

            self.assertIsNone(ledger.claim(183, "0f1e2d3"))
            self.assertIsNone(ledger.claim(184, "0f1e2d3"))
            self.assertEqual(ledger.claimed_work_items(), {183, 184})

    def test_renewing_extends_the_lease_of_the_holder(self) -> None:
        with TemporaryDirectory() as directory:
            ledger = AttemptLedger(Path(directory) / "attempts.json", lease_seconds=60)
            attempt = ledger.claim(183, "0f1e2d3")

            renewed = ledger.renew(attempt.attempt_id)

        self.assertGreater(renewed.lease_expires_at, attempt.lease_expires_at)
        self.assertEqual(renewed.state, RUNNING)

    def test_a_dispatcher_cannot_close_an_attempt_taken_over_after_its_lease_expired(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "attempts.json"
            crashed_dispatcher = AttemptLedger(path, lease_seconds=0)
            abandoned = crashed_dispatcher.claim(183, "0f1e2d3")
            AttemptLedger(path).claim(183, "9a8b7c6")

            with self.assertRaisesRegex(AttemptLedgerError, "no longer held"):
                crashed_dispatcher.close(abandoned.attempt_id, SUCCEEDED)

    def test_the_heartbeat_renews_the_lease_while_a_session_runs(self) -> None:
        with TemporaryDirectory() as directory:
            ledger = AttemptLedger(Path(directory) / "attempts.json", lease_seconds=60)
            attempt = ledger.claim(183, "0f1e2d3")

            with lease_heartbeat(ledger, attempt.attempt_id, interval_seconds=0.01):
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and ledger.attempts()[0].lease_expires_at == attempt.lease_expires_at:
                    time.sleep(0.01)

            renewed = ledger.attempts()[0]

        self.assertGreater(renewed.lease_expires_at, attempt.lease_expires_at)

    def test_the_ledger_records_identifiers_only(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "attempts.json"
            AttemptLedger(path).claim(183, "0f1e2d3")

            document = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            set(document["attempts"][0]),
            {
                "attempt_id",
                "work_item_id",
                "source_revision",
                "state",
                "lease_owner",
                "lease_expires_at",
                "retry_count",
                "started_at",
                "updated_at",
            },
        )

    def test_an_unusable_ledger_is_reported_without_echoing_its_content(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "attempts.json"
            path.write_text('{"attempts": [{"unexpected": "secret-looking-value"}]}', encoding="utf-8")

            with self.assertRaises(AttemptLedgerError) as raised:
                AttemptLedger(path).claim(183, "0f1e2d3")

        self.assertEqual(str(raised.exception), "the attempt ledger is invalid")

    def test_a_ledger_written_by_powershell_with_a_bom_is_readable(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "attempts.json"
            AttemptLedger(path).claim(183, "0f1e2d3")
            path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8-sig")

            self.assertEqual(AttemptLedger(path).claimed_work_items(), {183})

    def test_the_lock_does_not_survive_a_completed_operation(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "attempts.json"
            AttemptLedger(path).claim(183, "0f1e2d3")

            self.assertFalse(path.with_suffix(".lock").exists())


if __name__ == "__main__":
    unittest.main()
