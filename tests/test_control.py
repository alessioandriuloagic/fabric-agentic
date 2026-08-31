import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from fabric_agentic.cli import main, render_text
from fabric_agentic.console import render_html
from fabric_agentic.control import describe_agent, describe_all


def write_agent(home: Path, agent: str, **overrides) -> Path:
    directory = home / f"{agent}-agent"
    clone = directory / "repository"
    (clone / ".git").mkdir(parents=True)
    key_path = directory / "github-app-private-key.pem"
    key_path.write_text("not a real key", encoding="utf-8")
    key_path.chmod(0o600)
    (directory / "state.json").write_text("{}", encoding="utf-8")

    config = {
        "github": {
            "owner": "example-org",
            "repository": "example-repo",
            "app_id": 4672750,
            "installation_id": 155470382,
            "private_key_path": str(key_path),
        },
        "agent": {"repository_path": str(clone), "claude_command": "claude"},
    }
    if agent == "dev":
        config["azure_devops"] = {"organization": "example", "project": "example"}
        config["dispatcher"] = {"tracker_type": "github_issues"}
    config.update(overrides)
    (directory / "dispatcher-config.json").write_text(json.dumps(config), encoding="utf-8")
    return directory


class ControlTests(unittest.TestCase):
    def test_reports_a_fully_provisioned_agent(self) -> None:
        with TemporaryDirectory() as directory:
            home = Path(directory)
            write_agent(home, "dev")

            status = describe_agent("dev", home)

            self.assertTrue(status.ready)
            self.assertEqual(status.missing, ())
            self.assertEqual(status.repository, "example-org/example-repo")

    def test_a_configured_agent_that_never_ran_is_still_ready(self) -> None:
        with TemporaryDirectory() as directory:
            home = Path(directory)
            (write_agent(home, "dev") / "state.json").unlink()

            status = describe_agent("dev", home)

            self.assertTrue(status.ready)
            self.assertEqual(status.activity, "nessun ciclo registrato")

    def test_reports_every_missing_piece_of_an_unprovisioned_agent(self) -> None:
        with TemporaryDirectory() as directory:
            status = describe_agent("review", Path(directory))

            self.assertFalse(status.ready)
            self.assertIn("configurazione", status.missing)
            self.assertIn("identità", status.missing)
            self.assertIn("clone dedicato", status.missing)

    @unittest.skipIf(os.name == "nt", "Windows does not expose POSIX mode bits")
    def test_rejects_a_private_key_readable_beyond_its_owner(self) -> None:
        with TemporaryDirectory() as directory:
            home = Path(directory)
            (write_agent(home, "review") / "github-app-private-key.pem").chmod(0o644)

            self.assertIn("chiave privata", describe_agent("review", home).missing)

    def test_rejects_an_unprovisioned_identity(self) -> None:
        with TemporaryDirectory() as directory:
            home = Path(directory)
            agent_directory = write_agent(home, "issue")
            config = json.loads((agent_directory / "dispatcher-config.json").read_text(encoding="utf-8"))
            config["github"]["installation_id"] = 0
            (agent_directory / "dispatcher-config.json").write_text(json.dumps(config), encoding="utf-8")

            self.assertIn("identità", describe_agent("issue", home).missing)

    def test_rejects_a_section_the_dispatcher_reads_but_the_configuration_omits(self) -> None:
        with TemporaryDirectory() as directory:
            home = Path(directory)
            agent_directory = write_agent(home, "dev")
            config = json.loads((agent_directory / "dispatcher-config.json").read_text(encoding="utf-8"))
            del config["azure_devops"]
            (agent_directory / "dispatcher-config.json").write_text(json.dumps(config), encoding="utf-8")

            self.assertIn("configurazione", describe_agent("dev", home).missing)

    def test_rejects_a_tracker_left_to_the_silent_default(self) -> None:
        with TemporaryDirectory() as directory:
            home = Path(directory)
            agent_directory = write_agent(home, "dev")
            config = json.loads((agent_directory / "dispatcher-config.json").read_text(encoding="utf-8"))
            del config["dispatcher"]
            (agent_directory / "dispatcher-config.json").write_text(json.dumps(config), encoding="utf-8")

            self.assertIn("tracker", describe_agent("dev", home).missing)

    def test_every_agent_starts_a_continuous_loop(self) -> None:
        with TemporaryDirectory() as directory:
            home = Path(directory)

            for agent in ("issue", "dev", "review"):
                self.assertIn("--poll", describe_agent(agent, home).start_command)
            self.assertIn("--log", describe_agent("dev", home).start_command)
            self.assertNotIn("--log", describe_agent("review", home).start_command)

    def test_describes_the_whole_chain(self) -> None:
        with TemporaryDirectory() as directory:
            statuses = describe_all(Path(directory))

            self.assertEqual([status.agent for status in statuses], ["issue", "dev", "review"])

    def test_rejects_an_unknown_agent(self) -> None:
        with self.assertRaises(ValueError):
            describe_agent("auditor", Path("."))


class RenderingTests(unittest.TestCase):
    def test_the_page_never_carries_key_material(self) -> None:
        with TemporaryDirectory() as directory:
            home = Path(directory)
            write_agent(home, "dev")

            page = render_html(describe_all(home), home)

            self.assertNotIn("not a real key", page)
            self.assertIn("dev", page)
            self.assertIn("pronto", page)

    def test_the_text_report_lists_the_start_command(self) -> None:
        with TemporaryDirectory() as directory:
            home = Path(directory)

            report = render_text(describe_all(home), home)

            self.assertIn("python -m scripts.issue_dispatcher", report)


class CommandTests(unittest.TestCase):
    def doctor(self, home: str) -> int:
        with redirect_stdout(io.StringIO()):
            return main(["--home", home, "doctor"])

    def test_doctor_fails_when_an_agent_is_not_provisioned(self) -> None:
        with TemporaryDirectory() as directory:
            self.assertEqual(self.doctor(directory), 1)

    def test_doctor_passes_when_the_whole_chain_is_provisioned(self) -> None:
        with TemporaryDirectory() as directory:
            home = Path(directory)
            for agent in ("issue", "dev", "review"):
                write_agent(home, agent)

            self.assertEqual(self.doctor(directory), 0)


if __name__ == "__main__":
    unittest.main()
