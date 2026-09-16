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


LAKEHOUSE = "lh_demo"
TABLE = "demo_alessio"
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]

# The notebook reaches its Lakehouse by name instead of through a default Lakehouse binding: an
# item materialized by updateFromGit arrives without that binding, and work item #196 is run by
# hand. The workspace is the one the run happens in, so no workspace identifier is versioned here.
WORKSPACE_ID = notebookutils.runtime.context["currentWorkspaceId"]
LAKEHOUSE_PATH = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{LAKEHOUSE}.Lakehouse"
TABLE_PATH = f"{LAKEHOUSE_PATH}/Tables/{TABLE}"
RESULT_PATH = f"{LAKEHOUSE_PATH}/Files/agentic/demo_alessio_result.json"

# The single column approved on work item #196 (decision D8). Declared explicitly, because the
# runbook forbids silent inference, and kept as the whole contract: no technical metadata column.
TABLE_SCHEMA = StructType([
    StructField("names", StringType(), True),
])

# The literal row approved on the same work item. Decision D1 asks for a write on every run, so
# this is the content of the first write and of every rerun alike.
TABLE_ROWS = [{"names": "alessio"}]


def row_field(item, key: str):
    """Read one field of a notebookutils row, mapping-like on some runtimes, attribute-like on others."""
    return item[key] if isinstance(item, dict) else getattr(item, key)


def describe(schema: StructType) -> list[dict]:
    return [
        {"name": field.name, "type": field.dataType.simpleString(), "nullable": field.nullable}
        for field in schema.fields
    ]


def check_no_implicit_change(existing: StructType) -> None:
    # The row is rewritten on every run, the schema never is: a divergence is a specification
    # defect and fails the run instead of being reconciled by the notebook.
    if describe(existing) != describe(TABLE_SCHEMA):
        raise RuntimeError(f"{TABLE} exists with a schema that differs from the declared one")


def ensure_lakehouse() -> str:
    """Resolve the Lakehouse, creating it when the Git sync has not materialized it.

    Decision D2 on work item #196 authorizes any automatic creation path, so a missing Lakehouse is
    created here rather than left to a manual step.
    """
    if LAKEHOUSE in [row_field(item, "displayName") for item in notebookutils.lakehouse.list()]:
        return "already_exists"
    notebookutils.lakehouse.create(LAKEHOUSE)
    return "created"


def lakehouse_tables() -> list[str]:
    return [row_field(item, "name") for item in notebookutils.lakehouse.listTables(LAKEHOUSE)]


def write_row(table_exists: bool) -> str:
    """Write the declared row, replacing the previous content of an existing table."""
    if table_exists:
        check_no_implicit_change(spark.read.format("delta").load(TABLE_PATH).schema)
    (spark.createDataFrame(TABLE_ROWS, TABLE_SCHEMA)
        .write.format("delta").mode("overwrite").save(TABLE_PATH))
    return "overwritten" if table_exists else "created"


# CELL ********************
lakehouse_status = ensure_lakehouse()
status = write_row(TABLE in lakehouse_tables())

written = spark.read.format("delta").load(TABLE_PATH)
check_no_implicit_change(written.schema)
# A Delta table written by path is expected to appear among the Lakehouse tables. Reading the list
# back turns a surprise into an explicit failure instead of a green run over an invisible table.
if TABLE not in lakehouse_tables():
    raise RuntimeError(f"{TABLE} was written but does not appear among the tables of {LAKEHOUSE}")

evidence = {
    "outcome": "success",
    "run_id": RUN_ID,
    "workspace_id": WORKSPACE_ID,
    "lakehouse": LAKEHOUSE,
    "lakehouse_status": lakehouse_status,
    "table": TABLE,
    "status": status,
    "columns": describe(written.schema),
    "row_count": written.count(),
    "values": [row["names"] for row in written.collect()],
}
notebookutils.fs.put(RESULT_PATH, json.dumps(evidence), True)
notebookutils.notebook.exit(json.dumps(evidence))

# METADATA ********************
# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
