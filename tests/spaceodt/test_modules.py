from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import SimpleNamespace

import pytest


MODULE_NAMES = [
    "people",
    "groups",
    "locations",
    "licenses",
    "calling_call_queues",
    "calling_hunt_groups",
    "calling_auto_attendants",
    "calling_virtual_lines",
    "calling_virtual_extensions",
    "calling_schedules",
    "calling_pstn_locations",
    "devices",
    "workspaces",
]


@dataclass
class WriterSpy:
    csv_writes: list[tuple[str, list[dict]]]
    json_writes: list[tuple[str, dict]]

    def write_module_csv(self, module: str, rows: list[dict]):
        self.csv_writes.append((module, rows))
        return f"{module}.csv"

    def write_module_json(self, module: str, payload: dict):
        self.json_writes.append((module, payload))
        return f"{module}.json"


@dataclass
class StatusSpy:
    records: list[dict]

    def record(self, **kwargs):
        self.records.append(kwargs)


class Endpoint:
    def __init__(self, detail_enabled: bool = True):
        self._detail_enabled = detail_enabled

    def list(self):
        return [{"id": "abc", "name": "Name", "display_name": "Display"}]

    def details(self, item_id):
        if not self._detail_enabled:
            raise AssertionError("details should not be called")
        return {"id": item_id, "foo": 1, "bar": 2}


@pytest.fixture
def fake_api():
    telephony = SimpleNamespace(
        callqueue=Endpoint(),
        hunt_group=Endpoint(),
        auto_attendant=Endpoint(),
        virtual_line=Endpoint(),
        virtual_extensions=Endpoint(),
        pstn=Endpoint(),
    )
    common = SimpleNamespace(schedules=Endpoint())

    return SimpleNamespace(
        people=Endpoint(),
        groups=Endpoint(),
        locations=Endpoint(),
        licenses=Endpoint(detail_enabled=False),
        devices=Endpoint(),
        workspaces=Endpoint(),
        telephony=telephony,
        common=common,
    )


@pytest.mark.parametrize("module_name", MODULE_NAMES)
def test_run_module_contract(fake_api, module_name):
    mod = import_module(f"SpaceOdT.modules.{module_name}")
    writers = WriterSpy(csv_writes=[], json_writes=[])
    status = StatusSpy(records=[])

    result = mod.run_module(fake_api, writers, status)

    assert result.module == module_name
    assert result.count == 1
    assert result.csv_path == f"{module_name}.csv"
    assert result.json_path == f"{module_name}.json"
    assert len(writers.csv_writes) == 1
    assert len(writers.json_writes) == 1
    assert len(status.records) == 1

    payload = writers.json_writes[0][1]
    assert payload["module"] == module_name
    assert payload["count"] == 1

    if module_name == "licenses":
        assert result.raw_keys == []
    else:
        assert result.raw_keys == ["bar", "foo", "id"]
