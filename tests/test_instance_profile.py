import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fabric_agentic.instance_profile import (
    InstanceProfileError,
    feature_workspace_name,
    load_profile,
    parse_profile,
    workspace_name,
)


TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "profiles" / "template" / "instance.json"


def profile_document(**overrides) -> dict:
    document = {
        "schema_version": "1.0",
        "project": {"slug": "agentic", "display_name": "Fabric Agentic"},
        "tracker": {"type": "github_issues", "owner": "example-org", "repository": "example-repo"},
        "environments": ["dev", "test"],
        "sources": [
            {
                "name": "crm_demo",
                "connector": "crm_dataverse",
                "connection_ref": "fabric-connection://crm-demo",
                "datasets": [
                    {
                        "name": "accounts",
                        "primary_key": ["accountid"],
                        "load_mode": "incremental",
                        "watermark_column": "modifiedon",
                    }
                ],
            }
        ],
        "credentials": [{"name": "execution_credential", "store": "key_vault", "reference": "kv://vault/execution"}],
    }
    document.update(overrides)
    return document


class InstanceProfileTests(unittest.TestCase):
    def assertRejects(self, document: dict, message: str) -> None:
        with self.assertRaisesRegex(InstanceProfileError, message):
            parse_profile(document)

    # Contract

    def test_parses_a_valid_profile(self) -> None:
        profile = parse_profile(profile_document())

        self.assertEqual(profile.project_slug, "agentic")
        self.assertEqual(profile.tracker_type, "github_issues")
        self.assertEqual([dataset.name for source in profile.sources for dataset in source.datasets], ["accounts"])

    def test_loads_a_profile_from_disk(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "instance.json"
            path.write_text(json.dumps(profile_document()), encoding="utf-8")

            profile = load_profile(path)

        self.assertEqual(profile.project_slug, "agentic")

    def test_rejects_an_unsupported_schema_version(self) -> None:
        self.assertRejects(profile_document(schema_version="2.0"), "unsupported schema version")

    def test_rejects_an_invalid_project_slug(self) -> None:
        self.assertRejects(profile_document(project={"slug": "Agentic Demo", "display_name": "x"}), "project slug")

    def test_rejects_an_unsupported_tracker(self) -> None:
        document = profile_document()
        document["tracker"]["type"] = "trello"
        self.assertRejects(document, "unsupported tracker")

    def test_rejects_an_empty_environment_list(self) -> None:
        self.assertRejects(profile_document(environments=[]), "at least one environment")

    def test_rejects_an_unknown_connector(self) -> None:
        document = profile_document()
        document["sources"][0]["connector"] = "carrier_pigeon"
        self.assertRejects(document, "unknown connector")

    def test_rejects_a_dataset_without_a_primary_key(self) -> None:
        document = profile_document()
        document["sources"][0]["datasets"][0]["primary_key"] = []
        self.assertRejects(document, "primary key")

    def test_rejects_an_incremental_dataset_without_a_watermark(self) -> None:
        document = profile_document()
        del document["sources"][0]["datasets"][0]["watermark_column"]
        self.assertRejects(document, "watermark")

    def test_rejects_a_full_dataset_that_declares_a_watermark(self) -> None:
        document = profile_document()
        document["sources"][0]["datasets"][0]["load_mode"] = "full"
        self.assertRejects(document, "watermark")

    def test_rejects_a_duplicated_dataset_name(self) -> None:
        document = profile_document()
        document["sources"][0]["datasets"].append(dict(document["sources"][0]["datasets"][0]))
        self.assertRejects(document, "twice")

    # Secret hygiene

    def test_rejects_an_inline_credential_value(self) -> None:
        document = profile_document()
        document["credentials"][0]["value"] = "super-secret"
        self.assertRejects(document, "must reference")

    def test_rejects_a_credential_without_a_reference(self) -> None:
        document = profile_document()
        del document["credentials"][0]["reference"]
        self.assertRejects(document, "must reference")

    # Deterministic naming

    def test_derives_workspace_names_from_the_project_slug(self) -> None:
        profile = parse_profile(profile_document())

        self.assertEqual(workspace_name(profile, "dev"), "ws_agentic_dev")
        self.assertEqual(feature_workspace_name(profile, 42), "ws_agentic_feature_wi42")

    def test_refuses_a_workspace_for_an_undeclared_environment(self) -> None:
        profile = parse_profile(profile_document())

        with self.assertRaisesRegex(InstanceProfileError, "not declared"):
            workspace_name(profile, "prod")

    # Versioned template

    def test_the_shipped_template_profile_is_valid(self) -> None:
        profile = load_profile(TEMPLATE_PATH)

        self.assertTrue(profile.project_slug)
        self.assertTrue(profile.environments)


if __name__ == "__main__":
    unittest.main()
