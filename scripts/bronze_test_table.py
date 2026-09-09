"""Declared schema and idempotent creation decision for the Bronze `test` table."""

from dataclasses import dataclass


class BronzeTestTableError(ValueError):
    """Raised when the existing Bronze table diverges from the declared column contract."""


BRONZE_TABLE = "test"

# Column contract mirrored by fabric/notebook/nb_create_bronze_test.Notebook: name, order, type
# and nullability must match. Work item #182 approved a single string column and no other column.
COLUMNS = (("name", "string", True),)


@dataclass(frozen=True)
class CreationPlan:
    status: str
    columns: tuple[tuple[str, str, bool], ...]


def plan_creation(existing_columns: tuple | list | None = None) -> CreationPlan:
    """Decide what a run must do, so a rerun neither recreates the table nor alters its schema.

    `existing_columns` is `None` when the Delta table is absent, otherwise the columns read from
    the catalog. A divergence is reported instead of being reconciled: changing the schema of an
    existing table is a specification decision, not something a rerun may do implicitly.
    """
    if existing_columns is None:
        return CreationPlan("created", COLUMNS)
    if tuple(tuple(column) for column in existing_columns) != COLUMNS:
        raise BronzeTestTableError(f"{BRONZE_TABLE} exists with a schema that differs from the declared one")
    return CreationPlan("already_exists", COLUMNS)
