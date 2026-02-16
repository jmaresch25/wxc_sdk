from __future__ import annotations

from Space_OdT.modules.catalog import locations_row, people_row, workspaces_row
from Space_OdT.modules.v1_manifest import _row_from_item


def test_locations_row_exposes_language_and_address_fields() -> None:
    row = locations_row(
        {
            'id': 'loc1',
            'name': 'Madrid',
            'orgId': 'org1',
            'timeZone': 'Europe/Madrid',
            'preferredLanguage': 'es_ES',
            'address': {
                'address1': 'Calle Mayor 1',
                'city': 'Madrid',
                'state': 'Madrid',
                'postalCode': '28001',
                'country': 'ES',
            },
        }
    )

    assert row['language'] == 'es_ES'
    assert row['address_1'] == 'Calle Mayor 1'
    assert row['city'] == 'Madrid'
    assert row['state'] == 'Madrid'
    assert row['postal_code'] == '28001'
    assert row['country'] == 'ES'


def test_people_and_workspaces_mark_webex_calling_enabled_from_location() -> None:
    prow = people_row({'id': 'p1', 'emails': ['a@b.c'], 'callingData': {'locationId': 'loc1'}})
    wrow = workspaces_row({'id': 'w1', 'displayName': 'WS1', 'locationId': 'loc2'})

    assert prow['webex_calling_enabled'] is True
    assert wrow['workspace_id'] == 'w1'
    assert wrow['webex_calling_enabled'] is True


def test_row_from_item_maps_group_route_direct_and_location_fields() -> None:
    row = _row_from_item(
        {
            'groupId': 'g1',
            'memberId': 'm1',
            'memberType': 'WORKSPACE',
            'routeGroupId': 'rg1',
            'connectionType': 'Local Gateway',
            'directNumber': '+34123',
            'preferredLanguage': 'es_ES',
            'address': {'address1': 'A', 'city': 'C', 'state': 'S', 'postalCode': 'P', 'country': 'ES'},
        },
        method_path='x.y',
        kwargs={},
    )

    assert row['group_id'] == 'g1'
    assert row['member_id'] == 'm1'
    assert row['member_type'] == 'WORKSPACE'
    assert row['route_group_id'] == 'rg1'
    assert row['connection_type'] == 'Local Gateway'
    assert row['direct_number'] == '+34123'
    assert row['language'] == 'es_ES'
    assert row['address_1'] == 'A'
    assert row['city'] == 'C'
    assert row['state'] == 'S'
    assert row['postal_code'] == 'P'
    assert row['country'] == 'ES'
