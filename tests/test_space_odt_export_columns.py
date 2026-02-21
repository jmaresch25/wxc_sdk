from __future__ import annotations

from Space_OdT.export_runner import _columns_for_module
from Space_OdT.modules.v1_manifest import columns_for_artifact


def test_location_details_uses_artifact_specific_columns() -> None:
    columns = _columns_for_module('location_details')

    assert 'first_name' not in columns
    assert 'last_name' not in columns
    assert 'member_type' not in columns
    assert 'route_group_id' not in columns
    assert 'connection_type' not in columns
    assert 'direct_number' not in columns
    assert columns[:2] == ['location_id', 'name']


def test_people_details_keeps_people_fields_and_drops_workspace_fields() -> None:
    columns = _columns_for_module('people_details')

    assert 'workspace_id' not in columns
    assert 'license_id' not in columns
    assert 'virtual_line_id' not in columns
    assert 'group_id' not in columns
    assert 'route_group_id' not in columns
    assert 'connection_type' not in columns
    assert 'direct_number' in columns


def test_workspace_available_numbers_available_uses_number_inventory_shape() -> None:
    columns = _columns_for_module('workspace_available_numbers_available')

    assert 'workspace_id' in columns
    assert 'location_id' in columns
    assert 'id' in columns
    assert 'name' in columns
    assert 'direct_number' in columns
    assert 'first_name' not in columns
    assert 'last_name' not in columns
    assert 'member_type' not in columns
    assert 'person_id' not in columns
    assert 'license_id' not in columns
    assert 'virtual_line_id' not in columns
    assert 'group_id' not in columns
    assert 'route_group_id' not in columns
    assert 'connection_type' not in columns


def test_export_runner_and_manifest_column_projection_are_aligned() -> None:
    for module_name in ('location_details', 'people_details', 'workspace_available_numbers_available'):
        assert _columns_for_module(module_name) == columns_for_artifact(module_name)
