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

ENVIRONMENT_URL = "https://org12202591.crm4.dynamics.com"
TENANT_ID = "1cf6db06-3e00-48b6-a65c-be932526610e"
CLIENT_ID = "33e53b67-3872-4bc0-8d20-ed76a3c85ae7"
KEY_VAULT_URL = "https://kv-fabric-agentic-dev-01.vault.azure.net/"
CLIENT_SECRET_NAME = "fabric-agentic-key"


def resolve_access_token() -> str:
    client_secret = notebookutils.credentials.getSecret(KEY_VAULT_URL, CLIENT_SECRET_NAME)
    response = requests.post(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": client_secret,
            "scope": f"{ENVIRONMENT_URL}/.default",
            "grant_type": "client_credentials",
        },
        timeout=60,
    )
    if response.status_code != 200 or not response.json().get("access_token"):
        raise RuntimeError(f"CRM service-principal token acquisition failed with HTTP {response.status_code}")
    return response.json()["access_token"]


# CELL ********************
access_token = resolve_access_token()
response = requests.get(
    f"{ENVIRONMENT_URL}/api/data/v9.2/accounts/$count",
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
    "entity_set": "accounts",
    "source_count": int(response.text),
}))

# METADATA ********************
# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
