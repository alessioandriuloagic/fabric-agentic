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
from delta.tables import DeltaTable
from pyspark.sql import functions as F
from pyspark.sql.types import DateType, DecimalType, StringType, StructField, StructType


SOURCE_PATH = "Files/raw/pagamenti/pagamenti.csv"
BRONZE_TABLE = "pagamenti"
DATASET = "pagamenti"
PRIMARY_KEY = "ID_Pagamento"
DATE_FORMAT = "yyyy-MM-dd"
RESULT_PATH = "Files/agentic/ingest_pagamenti_result.json"
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]

# The File connector declares the schema explicitly: the runbook forbids silent inference.
SOURCE_SCHEMA = StructType([
    StructField("ID_Pagamento", StringType(), False),
    StructField("Data", DateType(), False),
    StructField("Cliente", StringType(), True),
    StructField("Importo", DecimalType(18, 2), False),
    StructField("Valuta", StringType(), True),
    StructField("Metodo_Pagamento", StringType(), True),
    StructField("Stato", StringType(), True),
    StructField("Numero_Fattura", StringType(), True),
    StructField("IBAN", StringType(), True),
    StructField("Note", StringType(), True),
])


def read_source():
    return (spark.read
        .schema(SOURCE_SCHEMA)
        .option("header", True)
        .option("dateFormat", DATE_FORMAT)
        .option("mode", "FAILFAST")
        .csv(SOURCE_PATH))


def check_primary_key(source) -> int:
    total = source.count()
    missing = source.where(F.col(PRIMARY_KEY).isNull() | (F.trim(F.col(PRIMARY_KEY)) == "")).count()
    distinct = source.select(PRIMARY_KEY).distinct().count()
    if missing or total != distinct:
        raise RuntimeError("pagamenti primary key check failed")
    return total


def check_reconcilable(source) -> None:
    # Runs before any write: Bronze keys absent from the source file mean the run is not a clean
    # full load, and the runbook forbids resolving that ambiguity without the owner.
    if not spark.catalog.tableExists(BRONZE_TABLE):
        return
    orphan = (spark.table(BRONZE_TABLE)
        .select(PRIMARY_KEY)
        .join(source.select(PRIMARY_KEY), on=PRIMARY_KEY, how="left_anti")
        .count())
    if orphan:
        raise RuntimeError("pagamenti reconciliation failed: Bronze holds keys absent from the source file")


def merge_bronze(source) -> int:
    staged = source.withColumn("_meta_ingested_at", F.current_timestamp())
    if not spark.catalog.tableExists(BRONZE_TABLE):
        staged.write.format("delta").saveAsTable(BRONZE_TABLE)
    else:
        target = DeltaTable.forName(spark, BRONZE_TABLE)
        (target.alias("target")
            .merge(staged.alias("source"), f"target.{PRIMARY_KEY} = source.{PRIMARY_KEY}")
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute())
    return spark.table(BRONZE_TABLE).count()


# CELL ********************
source = read_source().cache()
loaded_count = check_primary_key(source)
check_reconcilable(source)
destination_count = merge_bronze(source)
if destination_count != loaded_count:
    raise RuntimeError("pagamenti reconciliation failed")

evidence = {
    "schema_version": "1.3",
    "rail": "run_load",
    "outcome": "success",
    "run_id": RUN_ID,
    "dataset": DATASET,
    "source_path": SOURCE_PATH,
    "bronze_table": BRONZE_TABLE,
    "loaded_count": loaded_count,
    "total_destination_count": destination_count,
    "pk_check": "passed",
    "reconciliation": "passed",
}
notebookutils.fs.put(RESULT_PATH, json.dumps(evidence), True)
notebookutils.notebook.exit(json.dumps(evidence))

# METADATA ********************
# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
