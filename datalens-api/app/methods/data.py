import logging
import time
from typing import Any

from app.adapters.chart_result import normalize_chart
from app.adapters.data_request import (
    build_distinct_body,
    build_range_body,
    build_result_body,
    fields_from_schema,
)
from app.adapters.data_result import parse_result
from app.auth import AuthContext
from app.clients.charts_api import get_charts_client
from app.clients.data_api import DataApiClient, get_data_api_client
from app.config import get_settings
from app.errors import ApiError
from app.models.rpc_data import (
    GetChartDataArgs,
    GetChartDataResult,
    GetDatasetFieldValuesArgs,
    GetDatasetFieldValuesResult,
    QueryDatasetArgs,
    QueryDatasetResult,
)
from app.request_context import current_request_id

logger = logging.getLogger("datalens_api.data")


class _CallLog:
    def __init__(self, method: str, **fields: Any) -> None:
        self._method = method
        self._fields = fields
        self._started = time.monotonic()
        self.backend: Any = None

    def failed(self, exc: Exception) -> None:
        self.done(exc.code if isinstance(exc, ApiError) else "INTERNAL")

    def done(self, status: str, **fields: Any) -> None:
        merged = {
            **self._fields,
            **fields,
            "backendStatus": getattr(self.backend, "last_status", None),
        }
        logger.info(
            "method=%s trace_id=%s status=%s duration_ms=%d %s",
            self._method,
            current_request_id(),
            status,
            int((time.monotonic() - self._started) * 1000),
            " ".join(f"{key}={value}" for key, value in merged.items()),
        )


def _check_limit(limit: int, maximum: int) -> None:
    if limit > maximum:
        raise ApiError(
            400,
            "INVALID_ARGUMENT",
            f"limit must be <= {maximum}",
            details={"limit": limit, "max": maximum},
        )


def _dataset_path(dataset_id: str, suffix: str) -> str:
    return f"/api/data/v2/datasets/{dataset_id}/{suffix}"


async def _dataset_fields(client: DataApiClient, dataset_id: str):
    return fields_from_schema(await client.get(_dataset_path(dataset_id, "fields")))


async def query_dataset(args: QueryDatasetArgs, _ctx: AuthContext) -> QueryDatasetResult:
    settings = get_settings()
    log = _CallLog(
        "queryDataset",
        datasetId=args.datasetId,
        fields=len(args.fields),
        calculated=len(args.calculatedFields),
        filters=len(args.filters),
    )
    try:
        _check_limit(args.limit, settings.data_max_rows)
        client = log.backend = await get_data_api_client()
        dataset_fields = await _dataset_fields(client, args.datasetId)
        body = build_result_body(
            fields=args.fields,
            calculated=args.calculatedFields,
            filters=args.filters,
            order_by=args.orderBy,
            dataset_fields=dataset_fields,
            limit=args.limit,
        )
        raw = await client.post(_dataset_path(args.datasetId, "result"), body)
        columns, rows, truncated = parse_result(
            raw, role="row", limit=args.limit, max_chars=settings.data_max_cell_chars
        )
    except Exception as exc:
        log.failed(exc)
        raise
    log.done("OK", rowCount=len(rows), truncated=truncated)
    return QueryDatasetResult(
        columns=columns, rows=rows, rowCount=len(rows), truncated=truncated
    )


async def get_dataset_field_values(
    args: GetDatasetFieldValuesArgs, _ctx: AuthContext
) -> GetDatasetFieldValuesResult:
    settings = get_settings()
    log = _CallLog(
        "getDatasetFieldValues",
        datasetId=args.datasetId,
        mode=args.mode,
        filters=len(args.filters),
    )
    try:
        if args.mode == "distinct":
            _check_limit(args.limit, settings.data_max_distinct)
        client = log.backend = await get_data_api_client()
        dataset_fields = await _dataset_fields(client, args.datasetId)
        if args.mode == "range":
            body, target = build_range_body(
                field=args.field, filters=args.filters, dataset_fields=dataset_fields
            )
            raw = await client.post(_dataset_path(args.datasetId, "result"), body)
            _, rows, _ = parse_result(
                raw, role="row", limit=1, max_chars=settings.data_max_cell_chars
            )
            low, high = (rows[0] + [None, None])[:2] if rows else (None, None)
            result = GetDatasetFieldValuesResult(field=target.title, min=low, max=high)
            log.done("OK", rowCount=len(rows))
            return result
        body, target = build_distinct_body(
            field=args.field,
            search=args.search,
            filters=args.filters,
            dataset_fields=dataset_fields,
            limit=args.limit,
        )
        raw = await client.post(_dataset_path(args.datasetId, "values/distinct"), body)
        _, rows, truncated = parse_result(
            raw, role="distinct", limit=args.limit, max_chars=settings.data_max_cell_chars
        )
    except Exception as exc:
        log.failed(exc)
        raise
    log.done("OK", rowCount=len(rows), truncated=truncated)
    return GetDatasetFieldValuesResult(
        field=target.title, values=[row[0] for row in rows if row], truncated=truncated
    )


async def get_chart_data(args: GetChartDataArgs, _ctx: AuthContext) -> GetChartDataResult:
    settings = get_settings()
    log = _CallLog("getChartData", chartId=args.chartId, params=len(args.params))
    try:
        client = log.backend = await get_charts_client()
        raw = await client.run(args.chartId, args.params)
        normalized = normalize_chart(
            raw, max_rows=settings.data_max_rows, max_chars=settings.data_max_cell_chars
        )
    except Exception as exc:
        log.failed(exc)
        raise
    log.done(
        "OK",
        visualization=normalized["visualization"],
        normalized=normalized["normalized"],
        rowCount=normalized["rowCount"],
        truncated=normalized["truncated"],
    )
    return GetChartDataResult(chartId=args.chartId, **normalized)
