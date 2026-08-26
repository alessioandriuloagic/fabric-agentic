# Notebook Artifacts

`nb_crm_preflight.Notebook` is a FabricGitSource notebook that validates the CRM Fabric
Connection against Dataverse with `$top=0` and returns only aggregate evidence. It does not read
account records or write data.

The shared runtime in `scripts/crm_load.py` now defines the staged contract: CRM records are
written under `Files/raw/<source_system>/<dataset>/<run_id>/` and the extraction returns counts
and a candidate watermark. The notebook must call this extraction contract and must not write
Bronze directly. Bronze merge, audit and watermark commit belong to the shared load step.

The versioned artifact `nb_crm_load.Notebook` now implements that contract with Dataverse
pagination, Delta Bronze merge, audit and post-audit watermark commit. The workflow
`.github/workflows/pipe_agent_crm_run_load.yml` deploys and runs it with OIDC in `dev`; the field execution
updates the notebook's default Lakehouse binding even when the item already exists. A rerun is
required because the 2026-08-23 execution completed without visible tables under the previous
unbound definition, before S1-04 can close.

The load notebook reads the service-principal secret directly from Azure Key Vault with
`notebookutils.credentials.getSecret`; the separate Fabric Key Vault connection is not required.

`nb_ingest_pagamenti.Notebook` is the File-connector counterpart requested by work item #72. It
reads `Files/raw/pagamenti/pagamenti.csv` from the default Lakehouse with an explicit schema in
`FAILFAST` mode, checks `ID_Pagamento` uniqueness before any write, and merges the rows into the
Delta table `pagamenti` on that key, so a rerun updates instead of duplicating. It needs no
credential: the file already lives in the Lakehouse, and the notebook contains no secret and no
connection identifier. The column contract it declares is mirrored by `scripts/pagamenti_load.py`,
which is what the unit tests exercise; `tests/test_pagamenti_load.py` fails if the two drift apart.
The dataset is documented in `docs/sources/pagamenti.md`.

All notebooks in this folder are versioned in the Fabric Git source format
(`notebook-content.py` plus `.platform`), which is the shape the rest of the repository already
uses. The JSON notebook that the Items API receives — `cells` plus `metadata` — is derived from
that source by `scripts/fabric_artifacts.notebook_definition`, which emits `format: ipynb` and a
single `notebook-content.ipynb` part.
