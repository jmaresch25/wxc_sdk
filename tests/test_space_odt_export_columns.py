from __future__ import annotations

from Space_OdT.export_runner import _columns_for_module
from Space_OdT.modules.v1_manifest import V1_ARTIFACT_SPECS, columns_for_artifact


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



def test_all_v1_artifacts_have_specific_column_projection() -> None:
    modules = {spec.module for spec in V1_ARTIFACT_SPECS}
    for module_name in modules:
        columns = columns_for_artifact(module_name)
        assert columns
        assert 'source_method' in columns
        assert 'raw_keys' in columns
        assert 'raw_json' in columns


def test_non_domain_columns_are_removed_from_key_artifacts() -> None:
    expectations = {
        'location_pstn_connection': {'forbidden': {'first_name', 'last_name', 'person_id', 'workspace_id'}},
        'group_members': {'forbidden': {'license_id', 'route_group_id', 'connection_type'}},
        'person_numbers': {'forbidden': {'workspace_id', 'license_id', 'member_type'}},
        'workspace_numbers': {'forbidden': {'person_id', 'license_id', 'member_type'}},
        'call_queue_details': {'forbidden': {'license_id', 'virtual_line_id', 'route_group_id'}},
    }
    for module_name, rules in expectations.items():
        columns = columns_for_artifact(module_name)
        for col in rules['forbidden']:
            assert col not in columns
