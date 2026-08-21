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
The CRM framework is not executable until S1-00 adds the staged extraction, Bronze merge, audit,
watermark artifacts, and the `run_load` rail.
