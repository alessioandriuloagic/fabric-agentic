import json
import re
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.review_vote_publish import (
    CHECKLIST_ITEMS,
    ReviewVoteError,
    main,
    publish_review_vote,
)


APP_JWT = "app-jwt-3f9c2a"
INSTALLATION_TOKEN = "ghs-installation-token-7b1e4d"
PRIVATE_KEY = "-----BEGIN RSA PRIVATE KEY-----\n" + "k" * 400 + "\n-----END RSA PRIVATE KEY-----\n"
HEAD_SHA = "9c1d4f0a7b2e5c8d3f6a1b4e7c0d3f6a9b2e5c8d"
APP_SLUG = "fabric-agentic-review-agent"
BOT_LOGIN = f"{APP_SLUG}[bot]"
CHECKLIST_PATH = Path(__file__).resolve().parents[1] / "docs" / "functional" / "04-checklist-review.md"
CHECKLIST_RESULTS = {"PASSATO", "RILIEVO", "NON APPLICABILE", "CORRETTO"}


def outcome_text(results: dict | None = None, vote: str = "VOTO: APPROVATO") -> str:
    results = results or {}
    lines = ["ESITO REVIEW - PR #97 - iterazione 1", ""]
    lines.extend(results.get(item, f"{item} PASSATO") for item in CHECKLIST_ITEMS)
    lines.extend(["", vote])
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

    def __init__(self, reviews: list | None = None, failing_path: str | None = None) -> None:
        self.requests: list[tuple[str, str]] = []
        self.reviews = list(reviews or [])
        self.failing_path = failing_path

    def __call__(self, request):
        path = request.full_url.split("api.github.com", 1)[1].split("?", 1)[0]
        self.requests.append((request.method, path))
        if path == self.failing_path:
            raise OSError("connection reset")
        if path == "/app":
            return FakeResponse({"slug": APP_SLUG})
        if path.endswith("/access_tokens"):
            return FakeResponse({"token": INSTALLATION_TOKEN, "expires_at": "2026-08-27T12:00:00Z"})
        if path.endswith("/reviews"):
            if request.method == "GET":
                return FakeResponse(self.reviews)
            body = json.loads(request.data.decode("utf-8"))
            self.reviews.append(
                {
                    "id": 4242,
                    "commit_id": body["commit_id"],
                    "body": body["body"],
                    "state": body["event"],
                    "user": {"login": BOT_LOGIN},
                }
            )
            return FakeResponse(self.reviews[-1])
        if re.fullmatch(r"/repos/[^/]+/[^/]+/pulls/\d+", path):
            return FakeResponse({"head": {"sha": HEAD_SHA}})
        raise AssertionError(f"unexpected request {request.method} {path}")

    def submissions(self) -> list[tuple[str, str]]:
        return [entry for entry in self.requests if entry == ("POST", "/repos/o/r/pulls/97/reviews")]

    def submitted_bodies(self) -> list[dict]:
        return [review for review in self.reviews if review.get("id") == 4242]


class FakeGit:
    def __init__(self, branch: str = "main", status: str = "", head: str = "c0ffee", upstream: str = "c0ffee") -> None:
        self.branch = branch
        self.status = status
        self.head = head
        self.upstream = upstream

    def __call__(self, arguments: list[str]) -> str:
        if arguments == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return self.branch
        if arguments == ["status", "--porcelain"]:
            return self.status
        if arguments == ["rev-parse", "HEAD"]:
            return self.head
        if arguments == ["rev-parse", "origin/main"]:
            return self.upstream
        raise AssertionError(f"unexpected git call {arguments}")


class ReviewVotePublishTests(unittest.TestCase):
    def publish(self, text: str, github: FakeGitHub, git: FakeGit | None = None) -> dict:
        with TemporaryDirectory() as directory:
            outcome_path = Path(directory) / "review-outcome.txt"
            outcome_path.write_text(text, encoding="utf-8")
            key_path = Path(directory) / "review-agent.pem"
            key_path.write_text(PRIVATE_KEY, encoding="utf-8")
            with patch("fabric_agentic.github_app_auth.jwt.encode", return_value=APP_JWT):
                return publish_review_vote(
                    outcome_path=outcome_path,
                    owner="o",
                    repository="r",
                    pull_request=97,
                    app_id="9999999",
                    installation_id="1111111",
                    key_path=key_path,
                    opener=github,
                    git=git or FakeGit(),
                )

    def assertRejects(self, text: str, message: str, git: FakeGit | None = None) -> None:
        github = FakeGitHub()
        with self.assertRaisesRegex(ReviewVoteError, message):
            self.publish(text, github, git)
        self.assertEqual(github.requests, [], "a rejected outcome must not reach GitHub")

    # Vote mapping

    def test_maps_approvato_to_the_approve_event(self) -> None:
        github = FakeGitHub()

        result = self.publish(outcome_text(), github)

        self.assertEqual(result["event"], "APPROVE")
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["rilievi"], 0)
        self.assertEqual(github.submitted_bodies()[0]["state"], "APPROVE")

    def test_maps_non_approvato_to_the_request_changes_event(self) -> None:
        github = FakeGitHub()
        text = outcome_text(
            {"E1": "E1 RILIEVO - docs/technical/03-rail-script.md non aggiornato"},
            vote="VOTO: NON APPROVATO - 1 rilievo aperto",
        )

        result = self.publish(text, github)

        self.assertEqual(result["event"], "REQUEST_CHANGES")
        self.assertEqual(result["rilievi"], 1)
        self.assertEqual(github.submitted_bodies()[0]["state"], "REQUEST_CHANGES")

    def test_publishes_the_outcome_verbatim_as_the_review_body(self) -> None:
        github = FakeGitHub()
        text = outcome_text({"F4": "F4 NON APPLICABILE - nessuna branch policy nel diff"})

        self.publish(text, github)

        self.assertEqual(github.submitted_bodies()[0]["body"], text.strip())

    # Single submission and idempotence

    def test_sends_exactly_one_review_submission(self) -> None:
        github = FakeGitHub()

        self.publish(outcome_text(), github)

        self.assertEqual(len(github.submissions()), 1)
        self.assertEqual([method for method, _ in github.requests].count("POST"), 2)  # token + review

    def test_a_second_run_on_the_same_head_sha_does_not_publish_again(self) -> None:
        github = FakeGitHub()

        first = self.publish(outcome_text(), github)
        second = self.publish(outcome_text(), github)

        self.assertEqual(first["status"], "published")
        self.assertEqual(second["status"], "already_published")
        self.assertEqual(len(github.submissions()), 1)

    def test_a_review_from_another_author_does_not_block_the_vote(self) -> None:
        github = FakeGitHub(
            reviews=[{"id": 1, "commit_id": HEAD_SHA, "user": {"login": "owner-human"}}]
        )

        result = self.publish(outcome_text(), github)

        self.assertEqual(result["status"], "published")
        self.assertEqual(len(github.submissions()), 1)

    def test_a_previous_review_on_another_head_sha_does_not_block_the_vote(self) -> None:
        github = FakeGitHub(
            reviews=[{"id": 1, "commit_id": "0" * 40, "user": {"login": BOT_LOGIN}}]
        )

        result = self.publish(outcome_text(), github)

        self.assertEqual(result["status"], "published")
        self.assertEqual(result["head_sha"], HEAD_SHA)

    # Malformed outcomes

    def test_rejects_a_missing_checklist_item(self) -> None:
        text = "\n".join(
            line for line in outcome_text().splitlines() if not line.startswith("C3")
        )
        self.assertRejects(text, "misses the checklist items C3")

    def test_rejects_a_duplicated_checklist_item(self) -> None:
        text = outcome_text().replace("B2 PASSATO", "B2 PASSATO\nB2 PASSATO")
        self.assertRejects(text, "checklist item 'B2' twice")

    def test_rejects_an_item_outside_the_closed_checklist(self) -> None:
        text = outcome_text().replace("F4 PASSATO", "F4 PASSATO\nG1 PASSATO")
        self.assertRejects(text, "unknown checklist item 'G1'")

    def test_rejects_an_unknown_result_value(self) -> None:
        text = outcome_text({"D2": "D2 QUASI PASSATO"})
        self.assertRejects(text, "checklist line 'D2' is malformed")

    def test_accepts_a_corrected_checklist_item(self) -> None:
        text = outcome_text({"D2": "D2 CORRETTO - rilievo corretto nella re-review"})

        outcome = self.publish(text, FakeGitHub())

        self.assertEqual(outcome["status"], "published")

    def test_rejects_non_applicabile_without_a_reason(self) -> None:
        text = outcome_text({"C2": "C2 NON APPLICABILE"})
        self.assertRejects(text, "'C2' is NON APPLICABILE without a reason")

    def test_rejects_an_approvato_vote_that_hides_a_rilievo(self) -> None:
        text = outcome_text({"A1": "A1 RILIEVO - naming non conforme"})
        self.assertRejects(text, "VOTO APPROVATO contradicts 1 rilievi")

    def test_rejects_a_non_approvato_vote_without_rilievi(self) -> None:
        text = outcome_text(vote="VOTO: NON APPROVATO - 1 rilievo aperto")
        self.assertRejects(text, "contradicts an outcome without rilievi")

    def test_rejects_a_vote_whose_count_does_not_match_the_rilievi(self) -> None:
        text = outcome_text(
            {"A1": "A1 RILIEVO - naming", "A2": "A2 RILIEVO - cartella"},
            vote="VOTO: NON APPROVATO - 1 rilievo aperto",
        )
        self.assertRejects(text, "declares 1 rilievi instead of 2")

    def test_rejects_an_outcome_without_a_vote(self) -> None:
        text = "\n".join(
            line for line in outcome_text().splitlines() if not line.startswith("VOTO")
        )
        self.assertRejects(text, "no VOTO line")

    def test_rejects_a_malformed_vote_line(self) -> None:
        self.assertRejects(outcome_text(vote="VOTO: FORSE"), "malformed VOTO line")

    def test_rejects_an_empty_outcome(self) -> None:
        self.assertRejects("   \n", "outcome is empty")

    # Publishing copy

    def test_rejects_a_publishing_copy_off_main(self) -> None:
        self.assertRejects(
            outcome_text(),
            "publishing copy is on 'feature/wi-97-review-vote-publisher'",
            FakeGit(branch="feature/wi-97-review-vote-publisher"),
        )

    def test_rejects_a_publishing_copy_with_uncommitted_changes(self) -> None:
        self.assertRejects(
            outcome_text(),
            "publishing copy has uncommitted changes",
            FakeGit(status=" M scripts/review_vote_publish.py"),
        )

    def test_rejects_a_publishing_copy_not_aligned_to_origin_main(self) -> None:
        self.assertRejects(
            outcome_text(),
            "not aligned to 'origin/main'",
            FakeGit(head="c0ffee", upstream="decaf0"),
        )

    # Secret hygiene

    def test_a_successful_run_prints_no_token_jwt_or_key_material(self) -> None:
        github = FakeGitHub()
        with TemporaryDirectory() as directory:
            outcome_path = Path(directory) / "review-outcome.txt"
            outcome_path.write_text(outcome_text(), encoding="utf-8")
            key_path = Path(directory) / "review-agent.pem"
            key_path.write_text(PRIVATE_KEY, encoding="utf-8")
            argv = [
                "review_vote_publish.py",
                "--outcome-path", str(outcome_path),
                "--owner", "o",
                "--repository", "r",
                "--pull-request", "97",
                "--app-id", "9999999",
                "--installation-id", "1111111",
                "--key-path", str(key_path),
            ]
            printed = StringIO()
            with patch("sys.argv", argv), patch("fabric_agentic.github_app_auth.jwt.encode", return_value=APP_JWT):
                with redirect_stdout(printed):
                    exit_code = main(opener=github, git=FakeGit())

            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(printed.getvalue())["status"], "published")
            self.assertNoSecrets(printed.getvalue(), key_path)
            self.assertNoSecrets(github.submitted_bodies()[0]["body"], key_path)
            self.assertEqual(
                sorted(entry.name for entry in Path(directory).iterdir()),
                ["review-agent.pem", "review-outcome.txt"],
                "the publisher must not leave a state file behind",
            )

    def test_a_failing_run_prints_no_token_jwt_or_key_material(self) -> None:
        github = FakeGitHub(failing_path="/repos/o/r/pulls/97/reviews")
        with TemporaryDirectory() as directory:
            outcome_path = Path(directory) / "review-outcome.txt"
            outcome_path.write_text(outcome_text(), encoding="utf-8")
            key_path = Path(directory) / "review-agent.pem"
            key_path.write_text(PRIVATE_KEY, encoding="utf-8")
            argv = [
                "review_vote_publish.py",
                "--outcome-path", str(outcome_path),
                "--owner", "o",
                "--repository", "r",
                "--pull-request", "97",
                "--app-id", "9999999",
                "--installation-id", "1111111",
                "--key-path", str(key_path),
            ]
            printed = StringIO()
            with patch("sys.argv", argv), patch("fabric_agentic.github_app_auth.jwt.encode", return_value=APP_JWT):
                with redirect_stdout(printed):
                    exit_code = main(opener=github, git=FakeGit())

            self.assertEqual(exit_code, 1)
            self.assertIn("error", json.loads(printed.getvalue()))
            self.assertNoSecrets(printed.getvalue(), key_path)

    def assertNoSecrets(self, text: str, key_path: Path) -> None:
        for secret in (INSTALLATION_TOKEN, APP_JWT, "BEGIN RSA PRIVATE KEY", "k" * 40, str(key_path)):
            self.assertNotIn(secret, text)

    # Closed checklist

    def test_the_publisher_validates_the_versioned_checklist(self) -> None:
        rows = re.findall(
            r"^\|\s*([A-F]\d)\s*\|", CHECKLIST_PATH.read_text(encoding="utf-8"), flags=re.MULTILINE
        )

        self.assertEqual(tuple(rows), CHECKLIST_ITEMS)

    def test_the_publisher_accepts_all_states_declared_by_the_checklist(self) -> None:
        checklist = CHECKLIST_PATH.read_text(encoding="utf-8")
        declared_states = set(re.findall(r"`(PASSATO|RILIEVO|NON APPLICABILE|CORRETTO)`", checklist))

        self.assertEqual(declared_states, CHECKLIST_RESULTS)


if __name__ == "__main__":
    unittest.main()
