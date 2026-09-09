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
from pyspark.sql.types import StringType, StructField, StructType


BRONZE_TABLE = "test"
RESULT_PATH = "Files/agentic/create_bronze_test_result.json"
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]

# The single column approved on work item #182. Declared explicitly, because the runbook forbids
# silent inference, and kept as the whole contract: no technical metadata, no business column.
TABLE_SCHEMA = StructType([
    StructField("name", StringType(), True),
])


def describe(schema: StructType) -> list[dict]:
    return [
        {"name": field.name, "type": field.dataType.simpleString(), "nullable": field.nullable}
        for field in schema.fields
    ]


def check_no_implicit_change(existing: StructType) -> None:
    # A rerun never widens, narrows or retypes an existing table: a divergence is escalated as a
    # specification defect, not resolved by the notebook.
    if describe(existing) != describe(TABLE_SCHEMA):
        raise RuntimeError(f"{BRONZE_TABLE} exists with a schema that differs from the declared one")


def create_table_if_missing() -> str:
    """Create the empty Delta table once; a rerun leaves the existing table untouched."""
    if spark.catalog.tableExists(BRONZE_TABLE):
        check_no_implicit_change(spark.table(BRONZE_TABLE).schema)
        return "already_exists"

    spark.createDataFrame([], TABLE_SCHEMA).write.format("delta").saveAsTable(BRONZE_TABLE)
    return "created"


# CELL ********************
status = create_table_if_missing()
final_schema = spark.table(BRONZE_TABLE).schema
check_no_implicit_change(final_schema)
row_count = spark.table(BRONZE_TABLE).count()

evidence = {
    "outcome": "success",
    "run_id": RUN_ID,
    "bronze_table": BRONZE_TABLE,
    "status": status,
    "columns": describe(final_schema),
    "row_count": row_count,
}
notebookutils.fs.put(RESULT_PATH, json.dumps(evidence), True)
notebookutils.notebook.exit(json.dumps(evidence))

# METADATA ********************
# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
