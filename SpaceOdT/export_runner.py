from __future__ import annotations

import argparse
import csv
import importlib
import inspect
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RESULT_OK = "ok"
RESULT_FORBIDDEN = "forbidden"
RESULT_NOT_FOUND = "not_found"
RESULT_ERROR = "error"


@dataclass(frozen=True)
class ModuleTask:
    module: str
    method: str
    output_file: str


# Orden fijo de ejecución (MVP): mantener esta secuencia estable.
DEFAULT_TASKS: tuple[ModuleTask, ...] = (
    ModuleTask(module="SpaceOdT.modules.organizations", method="export", output_file="organizations.json"),
    ModuleTask(module="SpaceOdT.modules.people", method="export", output_file="people.json"),
    ModuleTask(module="SpaceOdT.modules.workspaces", method="export", output_file="workspaces.json"),
)


@dataclass
class ModuleRunStatus:
    module: str
    method: str
    result: str
    http_status: int | None
    error: str
    count: int
    elapsed_ms: int


def _extract_http_status(exc: Exception) -> int | None:
    for attr in ("status_code", "status", "http_status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return status_code if isinstance(status_code, int) else None


def _classify_error(exc: Exception) -> tuple[str, int | None]:
    http_status = _extract_http_status(exc)

    if isinstance(exc, PermissionError) or http_status in (401, 403):
        return RESULT_FORBIDDEN, http_status

    if isinstance(exc, (ModuleNotFoundError, FileNotFoundError, AttributeError)) or http_status == 404:
        return RESULT_NOT_FOUND, http_status

    return RESULT_ERROR, http_status


def _extract_count(result: Any) -> int:
    if result is None:
        return 0
    if isinstance(result, int):
        return result
    if isinstance(result, dict) and isinstance(result.get("count"), int):
        return int(result["count"])
    if hasattr(result, "__len__"):
        try:
            return len(result)  # type: ignore[arg-type]
        except TypeError:
            return 0
    return 0


def _invoke(module_name: str, method_name: str, output_path: Path) -> Any:
    module = importlib.import_module(module_name)
    method = getattr(module, method_name)
    sig = inspect.signature(method)

    kwargs = {}
    if "output_path" in sig.parameters:
        kwargs["output_path"] = output_path
    elif "output_file" in sig.parameters:
        kwargs["output_file"] = output_path
    elif "path" in sig.parameters:
        kwargs["path"] = output_path

    return method(**kwargs)


def _ensure_empty_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")


def _append_status_csv(path: Path, rows: list[ModuleRunStatus]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()

    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["module", "method", "result", "http_status", "error", "count", "elapsed_ms"],
        )
        if write_header:
            writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    "module": row.module,
                    "method": row.method,
                    "result": row.result,
                    "http_status": "" if row.http_status is None else row.http_status,
                    "error": row.error,
                    "count": row.count,
                    "elapsed_ms": row.elapsed_ms,
                }
            )


def run_exports(tasks: tuple[ModuleTask, ...] = DEFAULT_TASKS, exports_dir: Path = Path(".artifacts/exports")) -> dict[str, int]:
    statuses: list[ModuleRunStatus] = []

    for task in tasks:
        output_path = exports_dir / task.output_file
        started = time.perf_counter()
        try:
            result = _invoke(module_name=task.module, method_name=task.method, output_path=output_path)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            statuses.append(
                ModuleRunStatus(
                    module=task.module,
                    method=task.method,
                    result=RESULT_OK,
                    http_status=None,
                    error="",
                    count=_extract_count(result),
                    elapsed_ms=elapsed_ms,
                )
            )
        except Exception as exc:  # noqa: BLE001 - clasificación controlada por _classify_error()
            classification, http_status = _classify_error(exc)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            _ensure_empty_file(output_path)
            statuses.append(
                ModuleRunStatus(
                    module=task.module,
                    method=task.method,
                    result=classification,
                    http_status=http_status,
                    error=f"{exc.__class__.__name__}: {exc}",
                    count=0,
                    elapsed_ms=elapsed_ms,
                )
            )

    _append_status_csv(exports_dir / "status.csv", statuses)

    summary = {
        "total": len(statuses),
        RESULT_OK: sum(1 for item in statuses if item.result == RESULT_OK),
        RESULT_FORBIDDEN: sum(1 for item in statuses if item.result == RESULT_FORBIDDEN),
        RESULT_NOT_FOUND: sum(1 for item in statuses if item.result == RESULT_NOT_FOUND),
        RESULT_ERROR: sum(1 for item in statuses if item.result == RESULT_ERROR),
    }
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ejecuta exports en orden fijo y registra status.csv")
    parser.add_argument(
        "--exports-dir",
        default=".artifacts/exports",
        help="Directorio donde se guardan artefactos y status.csv",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = run_exports(exports_dir=Path(args.exports_dir))
    print(
        "Export summary "
        f"total={summary['total']} ok={summary[RESULT_OK]} forbidden={summary[RESULT_FORBIDDEN]} "
        f"not_found={summary[RESULT_NOT_FOUND]} error={summary[RESULT_ERROR]}"
    )

    # Código no bloqueante: permitimos éxito parcial sin fallar el pipeline.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
