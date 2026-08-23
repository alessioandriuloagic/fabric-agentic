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
import uuid
from datetime import datetime, timezone

import notebookutils
import requests
from delta.tables import DeltaTable
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType


ENVIRONMENT_URL = "https://org12202591.crm4.dynamics.com"
TENANT_ID = "1cf6db06-3e00-48b6-a65c-be932526610e"
CLIENT_ID = "33e53b67-3872-4bc0-8d20-ed76a3c85ae7"
KEY_VAULT_URL = "https://kv-fabric-agentic-dev-01.vault.azure.net/"
CLIENT_SECRET_NAME = "fabric-agentic-key"
ENTITY_SET = "accounts"
BRONZE_TABLE = "crm_demo_accounts"
AUDIT_TABLE = "crm_demo_load_audit"
WATERMARK_TABLE = "crm_demo_watermark"
RESULT_PATH = "Files/agentic/run_load_result.json"
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


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


def read_watermark() -> str | None:
    if not spark.catalog.tableExists(WATERMARK_TABLE):
        return None
    rows = spark.table(WATERMARK_TABLE).orderBy(F.col("committed_at").desc()).limit(1).collect()
    return rows[0]["watermark"] if rows else None


def fetch_accounts(token: str, watermark: str | None) -> list[dict]:
    select = "accountid,name,modifiedon"
    url = f"{ENVIRONMENT_URL}/api/data/v9.2/{ENTITY_SET}?$select={select}&$orderby=modifiedon asc"
    if watermark:
        url += f"&$filter=modifiedon ge {watermark}"
    headers = {
        "Authorization": f"Bearer {token}",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
    }
    records = []
    while url:
        response = requests.get(url, headers=headers, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"CRM extraction failed with HTTP {response.status_code}")
        payload = response.json()
        records.extend(payload.get("value", []))
        url = payload.get("@odata.nextLink")
    return records


def write_staging(records: list[dict]) -> str:
    stage_path = f"Files/raw/crm_demo/accounts/{RUN_ID}"
    schema = StructType([
        StructField("accountid", StringType(), False),
        StructField("name", StringType(), True),
        StructField("modifiedon", StringType(), False),
    ])
    staged = spark.createDataFrame(records, schema=schema) if records else spark.createDataFrame([], schema)
    staged.write.mode("overwrite").json(stage_path)
    return stage_path


def load_bronze(staged_path: str, extracted_count: int, previous_watermark: str | None) -> dict:
    staged = spark.read.schema("accountid string, name string, modifiedon string").json(staged_path)
    duplicate_keys = staged.groupBy("accountid").count().where(F.col("count") > 1).count()
    if duplicate_keys:
        raise RuntimeError("CRM primary key check failed")

    staged = staged.withColumn("_meta_ingested_at", F.current_timestamp())
    if not spark.catalog.tableExists(BRONZE_TABLE):
        staged.write.format("delta").saveAsTable(BRONZE_TABLE)
    else:
        delta = DeltaTable.forName(spark, BRONZE_TABLE)
        (delta.alias("target")
            .merge(staged.alias("source"), "target.accountid = source.accountid")
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute())

    destination_count = spark.table(BRONZE_TABLE).count()
    candidate = staged.select(F.max("modifiedon").alias("watermark")).collect()[0]["watermark"]
    candidate = candidate or previous_watermark
    audit = spark.createDataFrame([(
        RUN_ID, "accounts", extracted_count, extracted_count, destination_count, "passed", candidate,
    )], "run_id string, dataset string, extracted_count long, loaded_count long, destination_count long, reconciliation string, watermark string")
    if spark.catalog.tableExists(AUDIT_TABLE):
        audit_delta = DeltaTable.forName(spark, AUDIT_TABLE)
        (audit_delta.alias("target")
            .merge(audit.alias("source"), "target.run_id = source.run_id")
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute())
    else:
        audit.write.format("delta").saveAsTable(AUDIT_TABLE)

    if candidate:
        committed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        watermark = spark.createDataFrame([(candidate, committed_at)], "watermark string, committed_at string")
        watermark.write.mode("append").format("delta").saveAsTable(WATERMARK_TABLE)
    return {"extracted_count": extracted_count, "destination_count": destination_count, "watermark": candidate}


# CELL ********************
confirmed_watermark = read_watermark()
token = resolve_access_token()
accounts = fetch_accounts(token, confirmed_watermark)
staging_path = write_staging(accounts)
load_result = load_bronze(staging_path, len(accounts), confirmed_watermark)

evidence = {
    "schema_version": "1.0",
    "rail": "run_load",
    "outcome": "success",
    "run_id": RUN_ID,
    "staging_path": staging_path,
    "dataset": "accounts",
    **load_result,
}
notebookutils.fs.put(RESULT_PATH, json.dumps(evidence), True)
notebookutils.notebook.exit(json.dumps(evidence))

# METADATA ********************
# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }