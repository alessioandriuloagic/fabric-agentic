# Pagamenti Source

| Field | Value |
|---|---|
| Source system | `pagamenti` |
| Connector type | File (CSV) |
| Source file | `attachments/72/pagamenti.csv` (versioned issue attachment) |
| Runtime source path | `Files/raw/pagamenti/pagamenti.csv` in the destination Lakehouse |
| Destination Lakehouse | `lh_bronze_crm_demo` |
| Data classification | Demo/synthetic only |

The file carries no credential. It does contain IBAN-shaped and customer-name-shaped values, so it is
handled as demo/synthetic data: rows are never copied into tickets, pull requests, logs, or rail
evidence. Only aggregate counts leave the workspace.

## Dataset

| Field | Value |
|---|---|
| Dataset | `pagamenti` |
| Bronze table | `pagamenti` |
| Primary key | `ID_Pagamento` |
| Load mode | Full, merged on the primary key |
| Watermark | None |
| Fabric artifact | `fabric/notebook/nb_ingest_pagamenti.Notebook` |
| Local runtime | `scripts/pagamenti_load.py` |

## Declared schema

The File connector declares the schema explicitly; silent inference is forbidden by
[03 — Runbook onboarding sorgente](../functional/03-runbook-onboarding-sorgente.md), section 6.

| Column | Type | Nullable |
|---|---|---|
| `ID_Pagamento` | string | No |
| `Data` | date | No |
| `Cliente` | string | Yes |
| `Importo` | decimal(18, 2) | No |
| `Valuta` | string | Yes |
| `Metodo_Pagamento` | string | Yes |
| `Stato` | string | Yes |
| `Numero_Fattura` | string | Yes |
| `IBAN` | string | Yes |
| `Note` | string | Yes |

Business column names keep the source spelling, as required by `CONTEXT.md` section 4. The only
added column is the technical metadata column `_meta_ingested_at`.

## Load sequence

1. Read the CSV with the declared schema in `FAILFAST` mode, so a parsing deviation stops the run
   instead of producing null columns.
2. Check `ID_Pagamento` uniqueness and non-nullity **before any write**.
3. Still before any write, check that the existing Bronze table holds no key absent from the source
   file. That would mean the run is not a clean full load, and the runbook forbids resolving the
   ambiguity without the owner: the run stops instead of merging.
4. Merge into the Delta table `pagamenti` on `ID_Pagamento`: an existing key is updated, a new key
   is inserted. A rerun therefore cannot duplicate rows.
5. Reconcile source and destination counts as a post-condition; a mismatch fails the run.
6. Publish aggregate evidence to `Files/agentic/ingest_pagamenti_result.json`.

## Open operational precondition

The notebook reads the file from the Lakehouse, not from the repository: a Fabric notebook has no
access to the Git working tree. Work item #72 does not say how `pagamenti.csv` reaches
`Files/raw/pagamenti/` in `lh_bronze_crm_demo`, and this branch does not invent a mechanism for it.
Until the owner decides, the file has to be present in that path before the notebook runs. The two
candidate mechanisms are an owner-side upload into OneLake, or a deploy step that copies
`attachments/72/pagamenti.csv` during the run — the second is new rail code and needs an explicit
decision, not a silent addition.

## Declared deviations from the conventions

These follow the explicit wording of work item #72 and are open for owner confirmation.

| Convention | Ticket instruction | Status |
|---|---|---|
| Bronze table named `<source_system>_<dataset>` (`CONTEXT.md` section 4) | Table named `pagamenti` | Ticket wording applied |
| Feature workspace derived from the work item ID (`CONTEXT.md` section 3.2) | Lakehouse located in `ws_agentic_feature_wi6` | Ticket wording applied |
| Onboarding by declarative configuration only (runbook section 3, step 1) | A dedicated notebook was requested | Ticket wording applied; see [09 — Framework gate](../technical/09-framework-gate.md) |

The metadata-driven configuration contract `schemas/crm-source-v1.0.json` is pinned to the CRM
Dataverse tracer and cannot express a File source. This dataset is therefore not declared in
`configuration/`, and no configuration or schema file was widened to accommodate it.
