from __future__ import annotations

from Space_OdT.export_runner import _build_licenses_no_pstn, _build_v1_requirements_status
from Space_OdT.modules.v1_manifest import _row_from_item


def test_group_member_workspace_infers_workspace_id() -> None:
    row = _row_from_item({'groupId': 'g1', 'memberId': 'w1', 'memberType': 'WORKSPACE'}, 'groups.members', {})

    assert row['group_id'] == 'g1'
    assert row['member_id'] == 'w1'
    assert row['workspace_id'] == 'w1'


def test_build_licenses_no_pstn_filters_and_maps_assignments() -> None:
    rows = _build_licenses_no_pstn(
        {
            'licenses': [
                {'license_id': 'l1', 'sku_or_name': 'WEBEX CALLING NO PSTN'},
                {'license_id': 'l2', 'sku_or_name': 'WEBEX CALLING PSTN'},
            ],
            'license_assigned_users': [
                {'license_id': 'l1', 'person_id': 'p1'},
                {'license_id': 'l2', 'person_id': 'p2'},
            ],
        }
    )

    assert rows == [
        {
            'entity_id': 'p1',
            'entity_type': 'user',
            'license_id': 'l1',
            'license_name': 'WEBEX CALLING NO PSTN',
            'is_pstn': False,
        }
    ]


def test_build_v1_requirements_status_marks_key_requirements() -> None:
    cache = {
        'call_queue_agents': [{'first_name': 'Ana', 'last_name': 'Lopez'}],
        'call_queue_forwarding': [{'id': 'f1'}],
        'groups': [{'group_id': 'g1'}],
        'group_members': [{'group_id': 'g1', 'member_id': 'p1'}],
        'licenses_no_pstn': [{'entity_id': 'p1'}],
        'location_pstn_connection': [{'route_group_id': 'rg1', 'connection_type': 'Local Gateway'}],
        'locations': [{'language': 'es_ES', 'address_1': 'A', 'city': 'C', 'state': 'S', 'postal_code': 'P', 'country': 'ES'}],
        'people': [{'webex_calling_enabled': True, 'location_id': 'loc1'}],
        'workspaces': [{'workspace_id': 'w1'}],
        'person_numbers': [{'directNumber': '+341'}],
        'calling_locations': [{'id': 'loc1'}],
        'calling_locations_details': [{'id': 'loc1'}],
    }

    rows = _build_v1_requirements_status(cache)
    by_id = {row['requirement_id']: row for row in rows}

    assert by_id['call_queue_details_names']['status'] == 'ok'
    assert by_id['licenses_no_pstn']['status'] == 'ok'
    assert by_id['workspace_id']['status'] == 'ok'
    assert by_id['api_orgid_locationid_validation']['status'] == 'ok'
    assert by_id['control_hub_validation']['status'] == 'missing'
