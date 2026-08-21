# CRM Demo Source

| Field | Value |
|---|---|
| Source system | `crm_demo` |
| Connector type | `crm_dataverse` |
| Fabric Connection | `b838644d-afd9-4ec3-973d-e36ed85ad167` |
| Connection type | `CommonDataService` |
| Environment | `https://org4009cd0e.crm4.dynamics.com` |
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
`nb_crm_load` implements the same sequence on Delta tables. The `run_load` rail publishes the
v1.0 structured result through `scripts/run_load.py` or the OIDC workflow. Field verification
against the feature workspace is still open; `test` and `prod` remain unchanged and out of scope.
