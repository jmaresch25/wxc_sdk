from __future__ import annotations

import csv
from pathlib import Path

from SpaceOdT import export_runner


class _HTTPError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def test_run_exports_records_status_and_creates_empty_file_on_failure(monkeypatch, tmp_path: Path):
    tasks = (
        export_runner.ModuleTask("mod.ok", "run", "ok.json"),
        export_runner.ModuleTask("mod.forbidden", "run", "forbidden.json"),
        export_runner.ModuleTask("mod.notfound", "run", "missing.json"),
    )

    def fake_invoke(module_name: str, method_name: str, output_path: Path):
        if module_name == "mod.ok":
            output_path.write_text('{"items": [1,2]}', encoding="utf-8")
            return {"count": 2}
        if module_name == "mod.forbidden":
            raise _HTTPError("forbidden", 403)
        raise ModuleNotFoundError("missing module")

    monkeypatch.setattr(export_runner, "_invoke", fake_invoke)

    summary = export_runner.run_exports(tasks=tasks, exports_dir=tmp_path)

    assert summary["total"] == 3
    assert summary["ok"] == 1
    assert summary["forbidden"] == 1
    assert summary["not_found"] == 1
    assert summary["error"] == 0

    assert (tmp_path / "forbidden.json").exists()
    assert (tmp_path / "missing.json").exists()
    assert (tmp_path / "forbidden.json").read_text(encoding="utf-8") == ""

    with (tmp_path / "status.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert [row["result"] for row in rows] == ["ok", "forbidden", "not_found"]
    assert rows[0]["count"] == "2"
    assert rows[1]["http_status"] == "403"


def test_classify_error_maps_permission_and_404():
    forbidden, http_status = export_runner._classify_error(PermissionError("no"))
    assert forbidden == "forbidden"
    assert http_status is None

    not_found, http_status = export_runner._classify_error(_HTTPError("missing", 404))
    assert not_found == "not_found"
    assert http_status == 404
