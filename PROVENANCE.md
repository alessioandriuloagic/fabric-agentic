# Provenance

This file records patterns copied into Fabric Agentic from internal source repositories. Agentic
has no runtime dependency on any source repository.

| Target surface | Source repository | Source commit | Source paths/patterns | Copied by | Date | Divergence decision |
|---|---|---|---|---|---|---|
| CRM framework skeleton | `fabric-universal-connector` | `3303149c809172d0d320bfec353b5d81a` | CRM configuration shape, Fabric Connection auth boundary, OData pagination/change-tracking concepts, Bronze/audit/watermark separation | Alessio Andriulo | 2026-08-21 | Rewritten as CRM `accounts` configuration validation and pure request builder. The source connector directly writes Bronze and uses delta tokens; Agentic will keep extraction, Bronze merge, audit, and watermark as separate artifacts using `modifiedon`. |
| CRM preflight notebook | `fabric-universal-connector` | `3303149c809172d0d320bfec353b5d81a` | `CRMConnector` Fabric Connection authentication boundary and safe OData request concepts | Alessio Andriulo | 2026-08-21 | Rewritten as a read-only `$top=0` authorization preflight. The Agentic notebook returns only aggregate evidence and does not emit credentials or account records. |

## Review rule

Before expanding or updating a copied pattern, compare the relevant source revision with this
record. Record the adopted or deliberately rejected divergence in the pull request that changes
the Agentic implementation.
