# Fabric notebook source
# METADATA ********************
# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# CELL ********************
import json

import requests
import notebookutils

CONNECTION_ID = "b838644d-afd9-4ec3-973d-e36ed85ad167"
ENVIRONMENT_URL = "https://org4009cd0e.crm4.dynamics.com"


def resolve_access_token(connection_id: str) -> str:
    credential = notebookutils.connections.getCredential(connection_id)
    if isinstance(credential, dict):
        for key in ("accessToken", "access_token", "token"):
            value = credential.get(key)
            if isinstance(value, str) and value:
                return value
    raise RuntimeError("CRM Fabric Connection did not provide a supported access token")


# CELL ********************
access_token = resolve_access_token(CONNECTION_ID)
response = requests.get(
    f"{ENVIRONMENT_URL}/api/data/v9.2/accounts?$select=accountid&$top=0&$count=true",
    headers={
        "Authorization": f"Bearer {access_token}",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
    },
    timeout=60,
)

if response.status_code != 200:
    raise RuntimeError(f"CRM authorization preflight failed with HTTP {response.status_code}")

# Return only aggregate evidence. Never return connection credentials or account records.
notebookutils.notebook.exit(json.dumps({
    "outcome": "success",
    "connection_id": CONNECTION_ID,
    "entity_set": "accounts",
    "source_count": response.json().get("@odata.count"),
}))

# METADATA ********************
# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
