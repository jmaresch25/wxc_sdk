from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Callable


@dataclass(frozen=True)
class ModuleResult:
    module: str
    csv_path: str | None
    json_path: str | None
    count: int
    elapsed: float
    raw_keys: list[str]


@dataclass(frozen=True)
class ModuleSpec:
    module: str
    list_path: str
    detail_path: str | None
    columns: tuple[str, ...]
    id_field: str = "id"


def run_with_spec(
    spec: ModuleSpec,
    api: Any,
    writers: Any,
    status_recorder: Any,
) -> ModuleResult:
    started = perf_counter()
    items = _list_items(api=api, path=spec.list_path)
    rows = [_normalize_row(item=item, columns=spec.columns) for item in items]
    raw_keys = _extract_raw_keys(api=api, detail_path=spec.detail_path, rows=rows, id_field=spec.id_field)

    csv_path, json_path = _write_outputs(writers=writers, module=spec.module, rows=rows, raw_keys=raw_keys)

    elapsed = perf_counter() - started
    result = ModuleResult(
        module=spec.module,
        csv_path=csv_path,
        json_path=json_path,
        count=len(rows),
        elapsed=elapsed,
        raw_keys=raw_keys,
    )
    _record_status(status_recorder=status_recorder, result=result)
    return result


def _resolve_attr(obj: Any, dotted_path: str) -> Any:
    current = obj
    for chunk in dotted_path.split("."):
        current = getattr(current, chunk)
    return current


def _list_items(api: Any, path: str) -> list[dict[str, Any]]:
    list_fn = _resolve_attr(api, path)
    data = list_fn()
    return [_to_dict(item) for item in data]


def _normalize_row(item: dict[str, Any], columns: tuple[str, ...]) -> dict[str, Any]:
    return {column: item.get(column) for column in columns}


def _extract_raw_keys(api: Any, detail_path: str | None, rows: list[dict[str, Any]], id_field: str) -> list[str]:
    if not detail_path or not rows:
        return []
    first_id = rows[0].get(id_field)
    if not first_id:
        return []

    details_fn = _resolve_attr(api, detail_path)
    details = _safe_call_with_id(details_fn=details_fn, first_id=first_id)
    if details is None:
        return []

    details_dict = _to_dict(details)
    return sorted(details_dict.keys())


def _safe_call_with_id(details_fn: Callable[..., Any], first_id: Any) -> Any | None:
    attempt_kwargs = (
        {"id": first_id},
        {"person_id": first_id},
        {"group_id": first_id},
        {"location_id": first_id},
        {"queue_id": first_id},
        {"hunt_group_id": first_id},
        {"auto_attendant_id": first_id},
        {"workspace_id": first_id},
        {"virtual_line_id": first_id},
        {"extension_id": first_id},
        {"schedule_id": first_id},
        {"pstn_location_id": first_id},
        {"device_id": first_id},
    )
    try:
        return details_fn(first_id)
    except TypeError:
        for kwargs in attempt_kwargs:
            try:
                return details_fn(**kwargs)
            except TypeError:
                continue
    return None


def _write_outputs(writers: Any, module: str, rows: list[dict[str, Any]], raw_keys: list[str]) -> tuple[str | None, str | None]:
    payload = {
        "module": module,
        "count": len(rows),
        "rows": rows,
        "raw_keys": raw_keys,
    }

    csv_path: str | None = None
    json_path: str | None = None

    if hasattr(writers, "write_module_csv"):
        csv_path = writers.write_module_csv(module=module, rows=rows)
    elif hasattr(writers, "write_csv"):
        csv_path = writers.write_csv(module=module, rows=rows)

    if hasattr(writers, "write_module_json"):
        json_path = writers.write_module_json(module=module, payload=payload)
    elif hasattr(writers, "write_json"):
        json_path = writers.write_json(module=module, payload=payload)

    return csv_path, json_path


def _record_status(status_recorder: Any, result: ModuleResult) -> None:
    if hasattr(status_recorder, "record"):
        status_recorder.record(
            module=result.module,
            elapsed=result.elapsed,
            count=result.count,
            raw_keys=result.raw_keys,
            csv_path=result.csv_path,
            json_path=result.json_path,
        )
        return

    if hasattr(status_recorder, "append"):
        status_recorder.append(asdict(result))


def _to_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if hasattr(item, "to_dict"):
        return item.to_dict()
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if hasattr(item, "__dict__"):
        return {
            key: value
            for key, value in vars(item).items()
            if not key.startswith("_")
        }
    return {"value": item}
