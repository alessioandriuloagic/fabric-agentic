"""Registry of the source connectors an instance profile may declare."""

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote


class ConnectorError(Exception):
    """Raised without embedding connection material."""


@dataclass(frozen=True)
class DatasetRequest:
    """What the profile knows about one dataset, expressed without connector specifics."""

    name: str
    primary_key: tuple[str, ...]
    columns: tuple[str, ...] = ()
    watermark_column: str | None = None


@dataclass(frozen=True)
class RequestPlan:
    connector: str
    target: str
    merge_key: tuple[str, ...]
    incremental: bool


@dataclass(frozen=True)
class Connector:
    name: str
    supports_incremental: bool
    supports_source_count: bool
    connection_fields: tuple[str, ...]


CRM_DATAVERSE = Connector(
    name="crm_dataverse",
    supports_incremental=True,
    supports_source_count=True,
    connection_fields=("environment_url",),
)

# A dropped file exposes no server-side change marker, so it can only be read whole.
FILE = Connector(
    name="file",
    supports_incremental=False,
    supports_source_count=True,
    connection_fields=("path",),
)

_REGISTRY = {connector.name: connector for connector in (CRM_DATAVERSE, FILE)}

_SUGGESTED_CONNECTORS = (
    "business_central",
    "crm",
    "crm_dataverse",
    "database",
    "file",
    "oracle_database",
    "postgresql_database",
    "sharepoint",
    "sql_database",
)


def connector_names() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def suggested_connector_names() -> tuple[str, ...]:
    return _SUGGESTED_CONNECTORS


def get_connector(name: str) -> Connector:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ConnectorError(f"unknown connector '{name}'") from None


def supports_load_mode(name: str, load_mode: str) -> bool:
    return load_mode != "incremental" or get_connector(name).supports_incremental


def plan_request(
    name: str,
    connection: dict,
    request: DatasetRequest,
    watermark: datetime | None = None,
) -> RequestPlan:
    """Resolve one dataset read through the registry, so orchestration never branches per source."""
    connector = get_connector(name)
    missing = [field for field in connector.connection_fields if not connection.get(field)]
    if missing:
        raise ConnectorError(f"the connector '{name}' requires the connection field '{missing[0]}'")
    if not request.primary_key:
        raise ConnectorError(f"the dataset '{request.name}' must declare a primary key")

    if watermark is not None:
        if not connector.supports_incremental:
            raise ConnectorError(f"the connector '{name}' cannot read incrementally")
        if not request.watermark_column:
            raise ConnectorError(f"the dataset '{request.name}' must declare a watermark column")
        if watermark.tzinfo is None:
            raise ConnectorError("the watermark must include a timezone")

    return _PLANNERS[name](connector, connection, request, watermark)


def _plan_odata(
    connector: Connector,
    connection: dict,
    request: DatasetRequest,
    watermark: datetime | None,
) -> RequestPlan:
    base_url = str(connection["environment_url"]).rstrip("/")
    target = f"{base_url}/api/data/v9.2/{request.name}"

    query = []
    if request.columns:
        query.append("$select=" + ",".join(request.columns))
    if watermark is not None:
        moment = watermark.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        query.append("$filter=" + quote(f"{request.watermark_column} ge {moment}", safe=""))
    if query:
        target = f"{target}?{'&'.join(query)}"

    return RequestPlan(
        connector=connector.name,
        target=target,
        merge_key=request.primary_key,
        incremental=watermark is not None,
    )


def _plan_file(
    connector: Connector,
    connection: dict,
    request: DatasetRequest,
    watermark: datetime | None,
) -> RequestPlan:
    return RequestPlan(
        connector=connector.name,
        target=str(connection["path"]),
        merge_key=request.primary_key,
        incremental=False,
    )


_PLANNERS = {
    CRM_DATAVERSE.name: _plan_odata,
    FILE.name: _plan_file,
}
