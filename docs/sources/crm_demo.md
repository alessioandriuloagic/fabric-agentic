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

The local runtime now implements staged extraction, PK validation, idempotent Bronze merge,
per-run audit and post-audit watermark persistence in `scripts/crm_load.py`. The Fabric artifact
`nb_crm_load` implements the same sequence on Delta tables and reads the SP secret directly with
`notebookutils.credentials.getSecret`; it does not depend on a Fabric Key Vault connection. The
`run_load` rail publishes the
v1.0 structured result through `scripts/run_load.py` or the OIDC workflow. The deployer updates
the notebook binding even when the item already exists. The 2026-08-23 run completed technically
but showed no tables because this binding was missing; a rerun after the fix is required.
`test` and `prod` remain unchanged and out of scope.
