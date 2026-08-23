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
`.github/workflows/crm-run-load.yml` deploys and runs it with OIDC in `dev`; the field execution
updates the notebook's default Lakehouse binding even when the item already exists. A rerun is
required because the 2026-08-23 execution completed without visible tables under the previous
unbound definition, before S1-04 can close.

The load notebook reads the service-principal secret directly from Azure Key Vault with
`notebookutils.credentials.getSecret`; the separate Fabric Key Vault connection is not required.
