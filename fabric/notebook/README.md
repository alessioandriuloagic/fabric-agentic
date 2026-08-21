# Notebook Artifacts

`nb_crm_preflight.Notebook` is a FabricGitSource notebook that validates the CRM Fabric
Connection against Dataverse with `$top=0` and returns only aggregate evidence. It does not read
account records or write data.

S1-00 will next add a versioned CRM extraction notebook that stages `crm_demo/accounts` data under
`Files/raw/` and returns structured extraction counts. It must not write Bronze directly.
