# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "0f541025-c091-4f72-af8d-18137d7bd7d4",
# META       "default_lakehouse_name": "lh_bronze_crm_demo",
# META       "default_lakehouse_workspace_id": "c3465ab0-210b-4b31-86fd-03d9611fc037"
# META     }
# META   }
# META }

# CELL ********************

import json

import requests
import notebookutils

CONNECTION_ID = "b191e467-2922-4de5-a849-adbcdea88adc"
ENVIRONMENT_URL = "https://org12202591.crm4.dynamics.com"


def resolve_access_token(connection_id: str) -> str:
    credential = notebookutils.connections.getCredential(connection_id)
    if isinstance(credential, dict):
        for key in ("accessToken", "access_token", "token"):
            value = credential.get(key)
            if isinstance(value, str) and value:
                return value
    raise RuntimeError("CRM Fabric Connection did not provide a supported access token")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

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

# CELL ********************

credential = notebookutils.connections.getCredential(CONNECTION_ID)

print(type(credential).__name__)
print(type(credential.credential).__name__)

if isinstance(credential.credential, dict):
    print(list(credential.credential.keys()))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
