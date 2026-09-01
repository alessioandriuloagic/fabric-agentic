import unittest
from datetime import datetime, timezone

from fabric_agentic.connectors import (
    ConnectorError,
    DatasetRequest,
    connector_names,
    get_connector,
    plan_request,
    suggested_connector_names,
    supports_load_mode,
)


ACCOUNTS = DatasetRequest(
    name="accounts",
    primary_key=("accountid",),
    columns=("accountid", "name", "modifiedon"),
    watermark_column="modifiedon",
)
PAGAMENTI = DatasetRequest(name="pagamenti", primary_key=("ID_Pagamento",))

CRM_CONNECTION = {"environment_url": "https://example.crm4.dynamics.com/"}
FILE_CONNECTION = {"path": "/data/pagamenti.csv"}


class RegistryTests(unittest.TestCase):
    def test_declares_the_supported_connectors(self) -> None:
        self.assertEqual(connector_names(), ("crm_dataverse", "file"))

    def test_suggests_common_source_technologies_without_claiming_adapters_exist(self) -> None:
        self.assertEqual(
            suggested_connector_names(),
            (
                "business_central",
                "crm",
                "crm_dataverse",
                "database",
                "file",
                "oracle_database",
                "postgresql_database",
                "sharepoint",
                "sql_database",
            ),
        )

    def test_rejects_an_unknown_connector(self) -> None:
        with self.assertRaisesRegex(ConnectorError, "unknown connector"):
            get_connector("carrier_pigeon")

    def test_only_the_crm_connector_reads_incrementally(self) -> None:
        self.assertTrue(supports_load_mode("crm_dataverse", "incremental"))
        self.assertFalse(supports_load_mode("file", "incremental"))
        self.assertTrue(supports_load_mode("file", "full"))


class PlanningTests(unittest.TestCase):
    def test_plans_a_full_read(self) -> None:
        plan = plan_request("crm_dataverse", CRM_CONNECTION, ACCOUNTS)

        self.assertEqual(
            plan.target,
            "https://example.crm4.dynamics.com/api/data/v9.2/accounts?$select=accountid,name,modifiedon",
        )
        self.assertEqual(plan.merge_key, ("accountid",))
        self.assertFalse(plan.incremental)

    def test_plans_an_incremental_read_from_the_declared_watermark_column(self) -> None:
        plan = plan_request(
            "crm_dataverse",
            CRM_CONNECTION,
            ACCOUNTS,
            datetime(2026, 8, 21, 14, 0, tzinfo=timezone.utc),
        )

        self.assertIn("$filter=modifiedon%20ge%202026-08-21T14%3A00%3A00Z", plan.target)
        self.assertTrue(plan.incremental)

    def test_plans_a_file_read(self) -> None:
        plan = plan_request("file", FILE_CONNECTION, PAGAMENTI)

        self.assertEqual(plan.target, "/data/pagamenti.csv")
        self.assertEqual(plan.merge_key, ("ID_Pagamento",))
        self.assertFalse(plan.incremental)

    def test_rejects_an_incremental_read_the_connector_cannot_perform(self) -> None:
        with self.assertRaisesRegex(ConnectorError, "cannot read incrementally"):
            plan_request("file", FILE_CONNECTION, PAGAMENTI, datetime(2026, 8, 21, tzinfo=timezone.utc))

    def test_rejects_a_missing_connection_field(self) -> None:
        with self.assertRaisesRegex(ConnectorError, "environment_url"):
            plan_request("crm_dataverse", {}, ACCOUNTS)

    def test_rejects_a_dataset_without_a_primary_key(self) -> None:
        with self.assertRaisesRegex(ConnectorError, "primary key"):
            plan_request("crm_dataverse", CRM_CONNECTION, DatasetRequest(name="accounts", primary_key=()))

    def test_rejects_a_naive_watermark(self) -> None:
        with self.assertRaisesRegex(ConnectorError, "timezone"):
            plan_request("crm_dataverse", CRM_CONNECTION, ACCOUNTS, datetime(2026, 8, 21, 14, 0))

    def test_rejects_a_watermark_without_a_declared_column(self) -> None:
        request = DatasetRequest(name="accounts", primary_key=("accountid",))

        with self.assertRaisesRegex(ConnectorError, "watermark column"):
            plan_request("crm_dataverse", CRM_CONNECTION, request, datetime(2026, 8, 21, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
