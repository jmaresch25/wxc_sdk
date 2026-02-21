from __future__ import annotations

from types import SimpleNamespace

import pytest
from Space_OdT.modules.v1_manifest import (
    ArtifactSpec,
    ParamSource,
    ParamSourceValidationError,
    _iter_kwargs,
    required_source_ids_per_artifact,
    run_artifact,
    hydrate_lookup_sources,
    validate_param_sources,
    V1_ARTIFACT_SPECS,
)
from Space_OdT.modules.common import as_list, model_to_dict


class _FakeError(Exception):
    def __init__(self, code: int):
        super().__init__(f"error {code}")
        self.code = code


def test_iter_kwargs_filters_by_required_field() -> None:
    cache = {
        'people': [
            {'person_id': 'p1', 'location_id': 'l1'},
            {'person_id': 'p2', 'location_id': ''},
            {'person_id': 'p3'},
        ]
    }
    spec = ArtifactSpec(
        module='person_permissions_in',
        method_path='person_settings.permissions_in.read',
        static_kwargs={},
        param_sources=(ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),),
    )

    kwargs = _iter_kwargs(cache, spec)

    assert kwargs == [{'entity_id': 'p1'}]


def test_iter_kwargs_adds_diagnostics_for_empty_sources() -> None:
    cache = {
        'people': [
            {'person_id': 'p1', 'location_id': ''},
            {'person_id': '', 'location_id': 'l1'},
        ]
    }
    spec = ArtifactSpec(
        module='person_permissions_in',
        method_path='person_settings.permissions_in.read',
        static_kwargs={},
        param_sources=(ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),),
    )

    diagnostics: list[dict] = []
    kwargs = _iter_kwargs(cache, spec, diagnostics=diagnostics)

    assert kwargs == []
    assert diagnostics == [{
        'source_module': 'people',
        'param_name': 'entity_id',
        'field': 'person_id',
        'required_field': 'location_id',
        'min_required': 1,
        'valid_ids_detected': 0,
        'cache_rows': 2,
        'sample_ids': [],
    }]


def test_validate_param_sources_raises_clear_message_with_requirements() -> None:
    spec = ArtifactSpec(
        module='group_members',
        method_path='groups.members',
        static_kwargs={},
        param_sources=(ParamSource('group_id', 'groups', 'group_id'),),
    )

    with pytest.raises(ParamSourceValidationError) as exc_info:
        validate_param_sources({'groups': [{'group_id': ''}]}, spec)

    message = str(exc_info.value)
    assert "Artifact 'group_members' no ejecutable" in message
    assert 'groups (group_id -> group_id): 0/1 IDs válidos' in message
    assert 'required_source_ids_per_artifact=' in message
    assert 'source_diagnostics=' in message


def test_required_source_ids_per_artifact_table() -> None:
    spec = ArtifactSpec(
        module='workspace_numbers',
        method_path='workspace_settings.numbers.read',
        static_kwargs={},
        param_sources=(ParamSource('workspace_id', 'workspaces', 'id'),),
    )

    assert required_source_ids_per_artifact(spec) == [{
        'artifact': 'workspace_numbers',
        'source_module': 'workspaces',
        'param_name': 'workspace_id',
        'field': 'id',
        'required_field': None,
        'min_required': 1,
    }]


def test_run_artifact_skips_resterror_4003() -> None:
    calls: list[str] = []

    def read(*, entity_id: str):
        calls.append(entity_id)
        if entity_id == 'bad':
            raise _FakeError(4003)
        return {'id': f'row-{entity_id}', 'name': 'ok'}

    api = SimpleNamespace(
        person_settings=SimpleNamespace(
            permissions_in=SimpleNamespace(read=read),
        )
    )
    spec = ArtifactSpec(
        module='person_permissions_in',
        method_path='person_settings.permissions_in.read',
        static_kwargs={},
        param_sources=(ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),),
    )
    cache = {
        'people': [
            {'person_id': 'good', 'location_id': 'loc'},
            {'person_id': 'bad', 'location_id': 'loc'},
        ]
    }

    result = run_artifact(api, spec, cache)

    assert calls == ['good', 'bad']
    assert result.count == 1
    assert result.rows[0]['id'] == 'row-good'
    assert result.rows[0]['source_method'] == 'person_settings.permissions_in.read'


def test_hydrate_lookup_sources_populates_people_cache_with_calling_data() -> None:
    def people_list(*, calling_data: bool = False):
        assert calling_data is True
        return [{'id': 'p1', 'callingData': {'locationId': 'loc-1'}}]

    api = SimpleNamespace(people=SimpleNamespace(list=people_list))
    spec = ArtifactSpec(
        module='person_numbers',
        method_path='person_settings.numbers.read',
        static_kwargs={},
        param_sources=(ParamSource('person_id', 'people', 'person_id', required_field='location_id'),),
    )
    cache: dict[str, list[dict]] = {'people': []}

    hydrate_lookup_sources(api, spec, cache)

    assert len(cache['people']) == 1
    assert cache['people'][0]['id'] == 'p1'
    assert cache['people'][0]['person_id'] == 'p1'
    assert cache['people'][0]['location_id'] == 'loc-1'


def test_run_artifact_auto_hydrates_lookup_sources_before_validating() -> None:
    def people_list(*, calling_data: bool = False):
        return [{'id': 'p1', 'callingData': {'locationId': 'loc-1'}}]

    def numbers_read(*, person_id: str):
        return [{'id': f'n-{person_id}', 'directNumber': '+349999'}]

    api = SimpleNamespace(
        people=SimpleNamespace(list=people_list),
        person_settings=SimpleNamespace(numbers=SimpleNamespace(read=numbers_read)),
    )
    spec = ArtifactSpec(
        module='person_numbers',
        method_path='person_settings.numbers.read',
        static_kwargs={},
        param_sources=(ParamSource('person_id', 'people', 'person_id', required_field='location_id'),),
    )

    result = run_artifact(api, spec, cache={'people': []})

    assert result.count == 1
    assert result.rows[0]['direct_number'] == '+349999'


def test_manifest_includes_artifacts_for_requested_calling_fields() -> None:
    by_module = {spec.module: spec for spec in V1_ARTIFACT_SPECS}

    assert by_module['location_details'].method_path == 'locations.details'
    assert by_module['calling_locations_details'].method_path == 'telephony.locations.details'
    assert by_module['location_pstn_connection'].method_path == 'telephony.pstn.read'
    assert by_module['people_details'].method_path == 'people.details'
    assert by_module['person_numbers'].method_path == 'person_settings.numbers.read'
    assert by_module['person_permissions_out'].method_path == 'person_settings.permissions_out.read'
    assert by_module['person_call_forwarding'].method_path == 'person_settings.forwarding.read'
    assert by_module['workspace_details'].method_path == 'workspaces.details'
    assert by_module['workspace_numbers'].method_path == 'workspace_settings.numbers.read'
    assert by_module['workspace_call_forwarding'].method_path == 'workspace_settings.forwarding.read'


def test_run_artifact_location_details_does_not_emit_person_name_fields() -> None:
    def details(*, location_id: str):
        return {
            'id': location_id,
            'name': 'HQ',
            'firstName': 'Wrong',
            'lastName': 'Field',
            'preferredLanguage': 'es_ES',
            'address': {
                'address1': 'Main St 1',
                'city': 'Madrid',
                'state': 'MD',
                'postalCode': '28001',
                'country': 'ES',
            },
        }

    api = SimpleNamespace(locations=SimpleNamespace(details=details))
    spec = ArtifactSpec(
        module='location_details',
        method_path='locations.details',
        static_kwargs={},
        param_sources=(ParamSource('location_id', 'locations', 'location_id'),),
    )
    cache = {'locations': [{'location_id': 'loc-1'}]}

    result = run_artifact(api, spec, cache)

    assert result.count == 1
    row = result.rows[0]
    assert 'last_name' not in row
    assert 'first_name' not in row
    assert row['location_id'] == 'loc-1'
    assert row['name'] == 'HQ'


class _FakePydantic:
    def __iter__(self):
        # Mimics pydantic/BaseModel iter behavior returning key/value tuples.
        return iter([('id', 'p1'), ('displayName', 'Ana')])

    def model_dump(self, **kwargs):
        return {'id': 'p1', 'displayName': 'Ana', 'emails': ['ana@example.com']}


def test_as_list_keeps_single_model_object() -> None:
    model = _FakePydantic()

    rows = as_list(model)

    assert rows == [model]


def test_model_to_dict_prefers_alias_dump_for_sdk_models() -> None:
    payload = model_to_dict(_FakePydantic())

    assert payload['id'] == 'p1'
    assert payload['displayName'] == 'Ana'
    assert payload['emails'] == ['ana@example.com']
