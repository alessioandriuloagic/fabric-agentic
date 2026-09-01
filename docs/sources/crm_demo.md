# CRM Demo Source

| Field | Value |
|---|---|
| Source system | `crm_demo` |
| Connector type | `crm_dataverse` |
| Fabric Connection | `b838644d-afd9-4ec3-973d-e36ed85ad167` |
| Connection type | `CommonDataService` |
| Environment | `https://org12202591.crm4.dynamics.com` |
| Data classification | Demo/synthetic only |

## First Dataset

| Field | Value |
|---|---|
| Dataset | `accounts` |
| Dataverse entity set | `accounts` |
| Bronze table | `crm_demo_accounts` |
| Primary key | `accountid` |
| Load mode | Incremental |
| Watermark | `modifiedon` |
| Watermark policy | Inclusive (`>=`), commit only after Bronze merge and audit |
| Projected columns | `accountid`, `name`, `modifiedon` |

The Fabric Connection owns all credential material. Configuration stores only its identifier.

The local runtime implements staged extraction, PK validation, idempotent Bronze merge,
per-run audit and post-audit watermark persistence in `scripts/crm_load.py`. The Fabric artifact
`nb_crm_load` implements the same sequence on Delta tables and reads the SP secret directly with
`notebookutils.credentials.getSecret`; it does not depend on a Fabric Key Vault connection. The
`run_load` rail publishes a **v1.3** structured result through `scripts/run_load.py` or the OIDC
workflow, on the success path and on the failure path alike. The deployer updates the notebook
binding even when the item already exists.
`test` and `prod` remain unchanged and out of scope.

The real run `32648577263` completed successfully on 2026-08-23 and materialized the Bronze,
audit and watermark tables in the feature Lakehouse. The execution evidence reports 10 rows in
`crm_demo_accounts`, one row in `crm_demo_load_audit`, and one row in `crm_demo_watermark`. Run
`32648994929` published `loaded_count=5`, `total_destination_count=10`, passed PK/reconciliation
checks, and watermark `2026-08-21T17:39:25Z`. Here 5 is the incremental delta and 10 is the total
Bronze after merge; the v1.3 rail contract distinguishes these counts explicitly.

Two gaps on this chain remain open and are tracked in
[`../technical/14-inventario-catena-crm-accounts.md`](../technical/14-inventario-catena-crm-accounts.md):
`reconciliation` is written as a literal instead of being computed from the counts, and the rail
reads its evidence from a fixed OneLake path that is not bound to the run it just submitted. The
initial/idempotent/delta run sequence and the SQL verification against the source evidence have
not been executed yet.
