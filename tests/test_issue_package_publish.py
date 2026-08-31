import json
import re
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.issue_package_publish import (
    PACKAGE_SECTIONS,
    IssuePackageError,
    main,
    publish_package,
)


APP_JWT = "app-jwt-1a2b3c"
INSTALLATION_TOKEN = "ghs-installation-token-9f8e7d"
PRIVATE_KEY = "-----BEGIN RSA PRIVATE KEY-----\n" + "k" * 400 + "\n-----END RSA PRIVATE KEY-----\n"
APP_SLUG = "fabric-agentic-issue-agent"
BOT_LOGIN = f"{APP_SLUG}[bot]"


def package_text(sections: dict | None = None, header: str = "PACCHETTO DI LAVORO - Work Item Design - CRM accounts") -> str:
    sections = sections or {}
    lines = [header, ""]
    for section in PACKAGE_SECTIONS:
        lines.append(section)
        if section != "APPROVAZIONE RICHIESTA":
            lines.extend([sections.get(section, f"contenuto di {section}"), ""])
    return "\n".join(lines) + "\n"


class FakeResponse:
    def __init__(self, payload) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, *_):
        return json.dumps(self.payload).encode("utf-8")


class FakeGitHub:
    """Serves the endpoints the publisher touches and records every request it receives."""

    def __init__(self, comments: list | None = None, failing_path: str | None = None) -> None:
        self.requests: list[tuple[str, str]] = []
        self.comments = list(comments or [])
        self.failing_path = failing_path

    def __call__(self, request):
        path = request.full_url.split("api.github.com", 1)[1].split("?", 1)[0]
        self.requests.append((request.method, path))
        if path == self.failing_path:
            raise OSError("connection reset")
        if path == "/app":
            return FakeResponse({"slug": APP_SLUG})
        if path.endswith("/access_tokens"):
            return FakeResponse({"token": INSTALLATION_TOKEN, "expires_at": "2026-08-31T12:00:00Z"})
        if path.endswith("/comments"):
            if request.method == "GET":
                return FakeResponse(self.comments)
            body = json.loads(request.data.decode("utf-8"))
            self.comments.append({"id": 7788, "body": body["body"], "user": {"login": BOT_LOGIN}})
            return FakeResponse(self.comments[-1])
        raise AssertionError(f"unexpected request {request.method} {path}")

    def submissions(self) -> list[tuple[str, str]]:
        return [entry for entry in self.requests if entry == ("POST", "/repos/o/r/issues/140/comments")]

    def published_body(self) -> str:
        return self.comments[-1]["body"]


class IssuePackagePublishTests(unittest.TestCase):
    def publish(self, text: str, github: FakeGitHub) -> dict:
        with TemporaryDirectory() as directory:
            package_path = Path(directory) / "work-package.txt"
            package_path.write_text(text, encoding="utf-8")
            key_path = Path(directory) / "issue-agent.pem"
            key_path.write_text(PRIVATE_KEY, encoding="utf-8")
            with patch("fabric_agentic.github_app_auth.jwt.encode", return_value=APP_JWT):
                return publish_package(
                    package_path=package_path,
                    owner="o",
                    repository="r",
                    issue=140,
                    app_id="8888888",
                    installation_id="2222222",
                    key_path=key_path,
                    opener=github,
                )

    def assertRejects(self, text: str, message: str) -> None:
        github = FakeGitHub()
        with self.assertRaisesRegex(IssuePackageError, message):
            self.publish(text, github)
        self.assertEqual(github.requests, [], "a rejected package must not reach GitHub")

    # Publication

    def test_publishes_the_package_as_one_comment(self) -> None:
        github = FakeGitHub()

        result = self.publish(package_text(), github)

        self.assertEqual(result["status"], "published")
        self.assertEqual(result["issue"], 140)
        self.assertEqual(len(github.submissions()), 1)

    def test_published_comment_identifies_the_issue_agent_and_keeps_the_package(self) -> None:
        github = FakeGitHub()
        text = package_text({"DOMANDE APERTE": "nessuna"})

        self.publish(text, github)

        body = github.published_body()
        self.assertIn("[fabric-agentic-issue-agent]", body)
        self.assertIn("DOMANDE APERTE", body)
        self.assertIn("nessuna", body)

    def test_a_second_run_on_the_same_package_does_not_publish_again(self) -> None:
        github = FakeGitHub()

        first = self.publish(package_text(), github)
        second = self.publish(package_text(), github)

        self.assertEqual(first["status"], "published")
        self.assertEqual(second["status"], "already_published")
        self.assertEqual(len(github.submissions()), 1)

    def test_a_comment_from_another_author_does_not_block_publication(self) -> None:
        github = FakeGitHub(comments=[{"id": 1, "body": "human note", "user": {"login": "owner-human"}}])

        result = self.publish(package_text(), github)

        self.assertEqual(result["status"], "published")

    def test_the_publisher_never_creates_or_closes_a_work_item(self) -> None:
        github = FakeGitHub()

        self.publish(package_text(), github)

        methods = {method for method, _ in github.requests}
        self.assertEqual(methods, {"GET", "POST"})
        self.assertTrue(all(path.endswith("/comments") for method, path in github.requests if method == "POST" and "access_tokens" not in path))

    # Malformed packages

    def test_rejects_an_empty_package(self) -> None:
        self.assertRejects("   \n", "package is empty")

    def test_rejects_a_missing_header(self) -> None:
        self.assertRejects(package_text(header="RIEPILOGO LAVORO"), "malformed header")

    def test_accepts_a_package_preceded_by_session_prose(self) -> None:
        github = FakeGitHub()
        text = "Both specialists reported. Two procedural notes first.\n\n" + package_text()

        result = self.publish(text, github)

        self.assertEqual(result["status"], "published")
        self.assertTrue(github.published_body().splitlines()[2].startswith("PACCHETTO DI LAVORO"))
        self.assertNotIn("Both specialists reported", github.published_body())

    def test_rejects_an_unknown_mode(self) -> None:
        self.assertRejects(
            package_text(header="PACCHETTO DI LAVORO - Analisi Libera - CRM"), "unknown mode"
        )

    def test_rejects_a_missing_section(self) -> None:
        text = "\n".join(
            line for line in package_text().splitlines() if line != "RISCHI E DECISIONI"
        )
        self.assertRejects(text, "misses the sections RISCHI E DECISIONI")

    def test_rejects_a_duplicated_section(self) -> None:
        text = package_text().replace("DOMANDE APERTE", "DOMANDE APERTE\nDOMANDE APERTE", 1)
        self.assertRejects(text, "reports the section 'DOMANDE APERTE' twice")

    def test_rejects_sections_out_of_order(self) -> None:
        text = package_text().replace("SINTESI", "TEMP_MARKER").replace("ARCHITETTURA (ralph)", "SINTESI").replace("TEMP_MARKER", "ARCHITETTURA (ralph)")
        self.assertRejects(text, "sections are out of order")

    def test_rejects_an_empty_section(self) -> None:
        text = package_text({"TICKET PROPOSTI": ""})
        self.assertRejects(text, "section 'TICKET PROPOSTI' is empty")

    # Secret hygiene

    def test_a_successful_run_prints_no_token_jwt_or_key_material(self) -> None:
        github = FakeGitHub()
        with TemporaryDirectory() as directory:
            package_path = Path(directory) / "work-package.txt"
            package_path.write_text(package_text(), encoding="utf-8")
            key_path = Path(directory) / "issue-agent.pem"
            key_path.write_text(PRIVATE_KEY, encoding="utf-8")
            argv = [
                "issue_package_publish.py",
                "--package-path", str(package_path),
                "--owner", "o",
                "--repository", "r",
                "--issue", "140",
                "--app-id", "8888888",
                "--installation-id", "2222222",
                "--key-path", str(key_path),
            ]
            printed = StringIO()
            with patch("sys.argv", argv), patch("fabric_agentic.github_app_auth.jwt.encode", return_value=APP_JWT):
                with redirect_stdout(printed):
                    exit_code = main(opener=github)

            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(printed.getvalue())["status"], "published")
            for secret in (INSTALLATION_TOKEN, APP_JWT, "BEGIN RSA PRIVATE KEY", str(key_path)):
                self.assertNotIn(secret, printed.getvalue())

    def test_a_failing_run_reports_an_error_without_secrets(self) -> None:
        github = FakeGitHub(failing_path="/repos/o/r/issues/140/comments")
        with TemporaryDirectory() as directory:
            package_path = Path(directory) / "work-package.txt"
            package_path.write_text(package_text(), encoding="utf-8")
            key_path = Path(directory) / "issue-agent.pem"
            key_path.write_text(PRIVATE_KEY, encoding="utf-8")
            argv = [
                "issue_package_publish.py",
                "--package-path", str(package_path),
                "--owner", "o",
                "--repository", "r",
                "--issue", "140",
                "--app-id", "8888888",
                "--installation-id", "2222222",
                "--key-path", str(key_path),
            ]
            printed = StringIO()
            with patch("sys.argv", argv), patch("fabric_agentic.github_app_auth.jwt.encode", return_value=APP_JWT):
                with redirect_stdout(printed):
                    exit_code = main(opener=github)

            self.assertEqual(exit_code, 1)
            self.assertIn("error", json.loads(printed.getvalue()))
            for secret in (INSTALLATION_TOKEN, APP_JWT, "BEGIN RSA PRIVATE KEY"):
                self.assertNotIn(secret, printed.getvalue())

    # Versioned contract

    def test_the_publisher_validates_the_versioned_package_contract(self) -> None:
        instructions = (Path(__file__).resolve().parents[1] / "agents" / "issue" / "INSTRUCTIONS.md").read_text(encoding="utf-8")

        for section in PACKAGE_SECTIONS:
            self.assertIn(section, instructions)


if __name__ == "__main__":
    unittest.main()
