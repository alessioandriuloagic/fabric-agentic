# Pipeline Artifacts

The shared local runtime and `run_load` rail now exist. The Fabric data pipeline must invoke staged
extraction followed by the shared Bronze load, audit and watermark commit, without source-specific
branching in orchestration. Its CI/CD wrapper must publish the same `rail-result` contract.

The OIDC wrapper `.github/workflows/crm-run-load.yml` now deploys and runs the notebook in the
feature workspace and publishes `rail-result.json`. A native Fabric Data Pipeline artifact is
still not added; the workflow is the current CI/CD rail. `test` and `prod` are intentionally
unchanged.

The notebook writes aggregate run evidence to `Files/agentic/run_load_result.json`; the deployer
reads that file through OneLake and propagates counts, reconciliation and watermark into the
published rail result.
