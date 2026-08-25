"""Explicit CSV typing and idempotent Bronze merge for the pagamenti file dataset."""

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


class PagamentiLoadError(ValueError):
    """Raised when the pagamenti source file or the Bronze merge violates the declared contract."""


PRIMARY_KEY = "ID_Pagamento"
BRONZE_TABLE = "pagamenti"
DECIMAL_PRECISION = 18
DECIMAL_SCALE = 2

# Column contract mirrored by fabric/notebook/nb_ingest_pagamenti.Notebook: order and names must match.
COLUMNS = (
    ("ID_Pagamento", "string"),
    ("Data", "date"),
    ("Cliente", "string"),
    ("Importo", "decimal"),
    ("Valuta", "string"),
    ("Metodo_Pagamento", "string"),
    ("Stato", "string"),
    ("Numero_Fattura", "string"),
    ("IBAN", "string"),
    ("Note", "string"),
)
NON_NULLABLE_COLUMNS = ("ID_Pagamento", "Data", "Importo")


@dataclass(frozen=True)
class LoadResult:
    loaded_count: int
    destination_count: int


def read_pagamenti(source_path: Path) -> list[dict]:
    """Parse the source CSV against the declared schema, failing fast on any deviation."""
    try:
        with source_path.open(encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames != [name for name, _ in COLUMNS]:
                raise PagamentiLoadError("pagamenti header does not match the declared schema")

            rows = []
            for line_number, raw in enumerate(reader, start=2):
                if None in raw or any(value is None for value in raw.values()):
                    raise PagamentiLoadError(f"pagamenti row {line_number} does not have the declared column count")
                rows.append(_typed_row(raw, line_number))
    except OSError as error:
        raise PagamentiLoadError("pagamenti source file is unavailable") from error
    return rows


def check_primary_key(rows: list[dict]) -> int:
    keys = [row.get(PRIMARY_KEY) for row in rows]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise PagamentiLoadError("pagamenti primary key check failed")
    return len(keys)


def merge_bronze(rows: list[dict], bronze: list[dict] | None = None) -> tuple[list[dict], LoadResult]:
    """Merge the source rows on the primary key so a rerun cannot duplicate Bronze rows."""
    loaded_count = check_primary_key(rows)
    merged = {row[PRIMARY_KEY]: row for row in (bronze or [])}
    for row in rows:
        merged[row[PRIMARY_KEY]] = row

    destination = list(merged.values())
    if len(destination) != loaded_count:
        raise PagamentiLoadError("pagamenti reconciliation failed")
    return destination, LoadResult(loaded_count, len(destination))


def _typed_row(raw: dict, line_number: int) -> dict:
    row = {}
    for name, kind in COLUMNS:
        value = raw[name].strip()
        if not value:
            if name in NON_NULLABLE_COLUMNS:
                raise PagamentiLoadError(f"pagamenti row {line_number} is missing required column {name}")
            row[name] = None
            continue
        row[name] = _cast(name, kind, value, line_number)
    return row


def _cast(name: str, kind: str, value: str, line_number: int):
    if kind == "date":
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise PagamentiLoadError(f"pagamenti row {line_number} column {name} is not an ISO date") from error
    if kind == "decimal":
        return _cast_decimal(name, value, line_number)
    return value


def _cast_decimal(name: str, value: str, line_number: int) -> Decimal:
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise PagamentiLoadError(f"pagamenti row {line_number} column {name} is not a decimal") from error
    if not amount.is_finite():
        raise PagamentiLoadError(f"pagamenti row {line_number} column {name} is not a finite decimal")

    digits = amount.as_tuple()
    if -digits.exponent > DECIMAL_SCALE or len(digits.digits) > DECIMAL_PRECISION:
        raise PagamentiLoadError(
            f"pagamenti row {line_number} column {name} exceeds decimal({DECIMAL_PRECISION}, {DECIMAL_SCALE})"
        )
    return amount
