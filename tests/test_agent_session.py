import json
import unittest

from fabric_agentic.agent_session import session_failure_reason


class AgentSessionTests(unittest.TestCase):
    def test_reports_the_api_error_status_of_a_quota_failure(self) -> None:
        stdout = json.dumps({
            "is_error": True,
            "subtype": "success",
            "terminal_reason": "api_error",
            "api_error_status": 429,
            "session_id": "c18475a5",
            "result": "You've hit your session limit",
        })

        reason = session_failure_reason(1, stdout)

        self.assertIn("exit=1", reason)
        self.assertIn("api_error_status=429", reason)
        self.assertIn("session_id=c18475a5", reason)

    def test_never_reports_the_session_transcript(self) -> None:
        stdout = json.dumps({"api_error_status": 429, "result": "secret-looking transcript text"})

        reason = session_failure_reason(1, stdout)

        self.assertNotIn("transcript", reason)
        self.assertNotIn("secret-looking", reason)

    def test_reports_the_exit_code_when_output_is_not_json(self) -> None:
        reason = session_failure_reason(2, "traceback: boom")

        self.assertEqual(reason, "exit=2")


if __name__ == "__main__":
    unittest.main()
