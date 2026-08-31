import unittest

from fabric_agentic.polling import PollingStopped, run_polling


class Cycle:
    """Records how often the loop ran and can be told to fail a given number of times."""

    def __init__(self, failures: int = 0, error: type[Exception] = RuntimeError):
        self.calls = 0
        self.failures = failures
        self.error = error

    def __call__(self) -> list:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error("cycle failed")
        return [{"issue": self.calls}]


class PollingTests(unittest.TestCase):
    def test_runs_the_requested_number_of_cycles(self) -> None:
        cycle = Cycle()

        report = run_polling(cycle, poll_seconds=30, errors=(RuntimeError,), cycles=3, sleep=lambda _: None)

        self.assertEqual(cycle.calls, 3)
        self.assertEqual(report.cycles, 3)
        self.assertEqual(report.failures, 0)

    def test_waits_between_cycles_but_not_after_the_last_one(self) -> None:
        waits: list[float] = []

        run_polling(Cycle(), poll_seconds=30, errors=(RuntimeError,), cycles=3, sleep=waits.append)

        self.assertEqual(waits, [30, 30])

    def test_reports_each_cycle(self) -> None:
        seen: list[list] = []

        run_polling(
            Cycle(),
            poll_seconds=30,
            errors=(RuntimeError,),
            cycles=2,
            sleep=lambda _: None,
            on_cycle=seen.append,
        )

        self.assertEqual(seen, [[{"issue": 1}], [{"issue": 2}]])

    def test_survives_a_transient_failure(self) -> None:
        cycle = Cycle(failures=1)
        reasons: list[str] = []

        report = run_polling(
            cycle,
            poll_seconds=30,
            errors=(RuntimeError,),
            cycles=3,
            sleep=lambda _: None,
            on_error=lambda error: reasons.append(str(error)),
        )

        self.assertEqual(report.failures, 1)
        self.assertEqual(reasons, ["cycle failed"])
        self.assertEqual(cycle.calls, 3)

    def test_stops_instead_of_relaunching_a_session_that_keeps_failing(self) -> None:
        cycle = Cycle(failures=99)

        with self.assertRaisesRegex(PollingStopped, "consecutive failed cycles"):
            run_polling(cycle, poll_seconds=30, errors=(RuntimeError,), sleep=lambda _: None)

        self.assertEqual(cycle.calls, 3)

    def test_a_recovered_cycle_resets_the_failure_budget(self) -> None:
        class Alternating:
            def __init__(self):
                self.calls = 0

            def __call__(self) -> list:
                self.calls += 1
                if self.calls % 2:
                    raise RuntimeError("cycle failed")
                return []

        cycle = Alternating()

        report = run_polling(cycle, poll_seconds=30, errors=(RuntimeError,), cycles=6, sleep=lambda _: None)

        self.assertEqual(report.failures, 3)

    def test_does_not_swallow_an_unexpected_error(self) -> None:
        with self.assertRaises(ValueError):
            run_polling(
                Cycle(failures=1, error=ValueError),
                poll_seconds=30,
                errors=(RuntimeError,),
                cycles=2,
                sleep=lambda _: None,
            )


if __name__ == "__main__":
    unittest.main()
