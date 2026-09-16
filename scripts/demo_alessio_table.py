"""Declared schema, literal row and write decision for the demo `demo_alessio` table."""

from dataclasses import dataclass


class DemoAlessioTableError(ValueError):
    """Raised when the existing demo table diverges from the declared column contract."""


LAKEHOUSE = "lh_demo"
TABLE = "demo_alessio"

# Column contract mirrored by fabric/notebook/nb_demo_alessio.Notebook: name, order, type and
# nullability must match. Work item #196 approved a single string column, `names` (decision D8).
COLUMNS = (("names", "string", True),)

# The literal row the notebook loads, approved on the same work item. Decision D1 asks for a write
# on every run, so these are the rows of the first write and of every rerun alike.
ROWS = ({"names": "alessio"},)


@dataclass(frozen=True)
class LoadPlan:
    status: str
    columns: tuple[tuple[str, str, bool], ...]
    rows_to_write: tuple[dict[str, str], ...]


def plan_load(existing_columns: tuple | list | None = None) -> LoadPlan:
    """Decide what a run must do, so a rerun rewrites the row without ever altering the schema.

    `existing_columns` is `None` when the Delta table is absent, otherwise the columns read from the
    table. Work item #196 asks for a write on every run — the table is a throwaway check of the
    chain, not a dataset that must stay untouched — so a rerun overwrites the content. A column
    contract that diverges from the declared one is reported instead: changing the schema of an
    existing table is a specification decision, not something a rerun may do implicitly.
    """
    if existing_columns is None:
        return LoadPlan("created", COLUMNS, ROWS)
    if tuple(tuple(column) for column in existing_columns) != COLUMNS:
        raise DemoAlessioTableError(f"{TABLE} exists with a schema that differs from the declared one")
    return LoadPlan("overwritten", COLUMNS, ROWS)
