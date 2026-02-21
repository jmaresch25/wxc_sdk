from __future__ import annotations

from types import SimpleNamespace
import csv

import pytest

from Space_OdT.v21.transformacion import launcher_csv_dependencias as launcher
from Space_OdT.v21.transformacion import usuarios_asignar_location_desde_csv as users_csv


class _ThrottledError(Exception):
    def __init__(self, retry_after: str):
        super().__init__('too many requests')
        self.response = SimpleNamespace(status_code=429, headers={'Retry-After': retry_after})


def test_retry_after_wait_seconds_accepts_numeric():
    assert launcher._retry_after_wait_seconds('5') == 5.0


def test_invoke_with_retry_after_retries_once(monkeypatch):
    sleep_calls: list[float] = []
    monkeypatch.setattr(launcher.time, 'sleep', lambda seconds: sleep_calls.append(seconds))

    calls = {'count': 0}

    def handler(*, token: str, **params):
        calls['count'] += 1
        if calls['count'] == 1:
            raise _ThrottledError('2')
        return {'status': 'ok', 'token': token, 'params': params}

    result = launcher._invoke_with_retry_after(handler=handler, token='tkn', params={'a': 1})

    assert result['status'] == 'ok'
    assert calls['count'] == 2
    assert sleep_calls == [2.0]


def test_invoke_with_retry_after_does_not_retry_without_header(monkeypatch):
    monkeypatch.setattr(launcher.time, 'sleep', lambda _: None)

    class _NoHeaderError(Exception):
        def __init__(self):
            self.response = SimpleNamespace(status_code=429, headers={})

    def handler(*, token: str, **params):
        raise _NoHeaderError()

    with pytest.raises(_NoHeaderError):
        launcher._invoke_with_retry_after(handler=handler, token='tkn', params={})


def test_read_parameter_map_from_columns_csv(tmp_path):
    csv_path = tmp_path / 'params.csv'
    csv_path.write_text('location_id,add_license_ids,person_id\nloc-1,"[""lic-a""]",person-1\n', encoding='utf-8')

    parameter_map = launcher._read_parameter_map(csv_path)

    assert parameter_map['location_id'] == 'loc-1'
    assert parameter_map['add_license_ids'] == ['lic-a']
    assert parameter_map['person_id'] == 'person-1'




def test_read_parameter_map_uses_first_non_empty_value_per_column(tmp_path):
    csv_path = tmp_path / 'params_rows.csv'
    csv_path.write_text(
        'person_id,remove_license_ids,org_id\n'
        ',,org-1\n'
        'person-2,"lic-a,lic-b",\n',
        encoding='utf-8',
    )

    parameter_map = launcher._read_parameter_map(csv_path)

    assert parameter_map['person_id'] == 'person-2'
    assert parameter_map['remove_license_ids'] == 'lic-a,lic-b'
    assert parameter_map['org_id'] == 'org-1'

def test_run_script_skips_when_required_dependency_is_missing():
    result = launcher._run_script(
        script_name='ubicacion_actualizar_cabecera',
        parameter_map={'location_id': 'loc1', 'phone_number': ''},
        token='tkn',
        auto_confirm=True,
        dry_run=False,
    )

    assert result['status'] == 'skipped'
    assert result['reason'] == 'missing_dependencies'
    assert result['missing_dependencies'] == 'phone_number'




def test_location_pstn_optional_dependencies_match_defaults():
    required = launcher.SCRIPT_DEPENDENCIES['ubicacion_configurar_pstn']

    assert 'location_id' in required
    assert 'premise_route_id' in required
    assert 'premise_route_type' not in required
    assert 'pstn_connection_type' not in required



def test_params_for_script_does_not_require_handler_defaults(monkeypatch):
    def _fake_handler(token, location_id, premise_route_id, pstn_connection_type='LOCAL_GATEWAY'):
        return {'status': 'ok'}

    monkeypatch.setitem(launcher.HANDLERS, 'ubicacion_configurar_pstn', _fake_handler)
    monkeypatch.setitem(launcher.SCRIPT_DEPENDENCIES, 'ubicacion_configurar_pstn', ['location_id', 'premise_route_id', 'pstn_connection_type'])

    params, missing = launcher._params_for_script(
        'ubicacion_configurar_pstn',
        {'location_id': 'loc-1', 'premise_route_id': 'rg-1'},
    )

    assert missing == []
    assert params['location_id'] == 'loc-1'
    assert params['premise_route_id'] == 'rg-1'
    assert 'pstn_connection_type' not in params

def test_run_script_parses_and_uses_supported_params(monkeypatch):
    def _fake_handler(token, person_id, add_license_ids, org_id=None):
        return {'status': 'ok', 'kwargs': {'person_id': person_id, 'add_license_ids': add_license_ids, 'org_id': org_id}}

    monkeypatch.setitem(launcher.HANDLERS, 'usuarios_modificar_licencias', _fake_handler)

    result = launcher._run_script(
        script_name='usuarios_modificar_licencias',
        parameter_map={
            'person_id': 'person-1',
            'add_license_ids': ['lic-a'],
            'org_id': 'org-1',
            'remove_license_ids': [],
            'active': True,
        },
        token='tkn',
        auto_confirm=True,
        dry_run=True,
    )

    assert result['status'] == 'dry_run'
    assert result['params']['add_license_ids'] == ['lic-a']
    assert 'active' not in result['params']


def test_run_script_coerces_comma_separated_values_for_list_params(monkeypatch):
    def _fake_handler(token, location_id: str, phone_numbers: list[str]):
        return {'status': 'ok'}

    monkeypatch.setitem(launcher.HANDLERS, 'ubicacion_alta_numeraciones_desactivadas', _fake_handler)

    result = launcher._run_script(
        script_name='ubicacion_alta_numeraciones_desactivadas',
        parameter_map={
            'location_id': 'loc-1',
            'phone_numbers': '+34932847561,+34935173024',
        },
        token='tkn',
        auto_confirm=True,
        dry_run=True,
    )

    assert result['status'] == 'dry_run'
    assert result['params']['phone_numbers'] == ['+34932847561', '+34935173024']


def test_launcher_supports_workspace_forwarding_telephony_script():
    assert 'workspaces_configurar_desvio_prefijo53_telephony' in launcher.HANDLERS

    result = launcher._run_script(
        script_name='workspaces_configurar_desvio_prefijo53_telephony',
        parameter_map={'workspace_id': 'w1', 'extension': '5102', 'destination': '539402744'},
        token='tkn',
        auto_confirm=True,
        dry_run=True,
    )

    assert result['status'] == 'dry_run'
    assert result['params']['workspace_id'] == 'w1'



def test_people_to_location_csv_headers_are_minimal_required_fields(tmp_path):
    people_json = tmp_path / 'people.json'
    people_json.write_text('[{"id":"person-1"}]', encoding='utf-8')
    csv_path = tmp_path / 'people_to_location.csv'

    users_csv.generate_csv_from_people_json(people_json=people_json, output_csv=csv_path, overwrite=True)

    with csv_path.open('r', encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == ['selected', 'person_id', 'target_location_id']
        first = next(reader)

    assert first['person_id'] == 'person-1'
    assert first['target_location_id'] == ''


def test_launcher_includes_people_to_location_csv_head_in_invocation(monkeypatch, tmp_path):
    report_csv = tmp_path / 'people_to_location.csv'
    report_csv.write_text('selected,person_id,target_location_id\n1,p-1,loc-1\n', encoding='utf-8')

    monkeypatch.setattr(launcher, 'generate_csv_from_people_json', lambda **kwargs: report_csv)

    result = launcher._run_script(
        script_name='usuarios_asignar_location_desde_csv',
        parameter_map={'csv_path': str(report_csv), 'people_json': str(tmp_path / 'people.json')},
        token='tkn',
        auto_confirm=True,
        dry_run=True,
    )

    assert result['status'] == 'dry_run'
    preview = result['invocation']['csv_preview']
    assert preview['exists'] is True
    assert preview['columns'] == ['selected', 'person_id', 'target_location_id']
    assert preview['head'][0]['person_id'] == 'p-1'


def test_apply_with_license_assignment_skips_if_user_already_in_target_location():
    person = SimpleNamespace(location_id='loc-1', extension='6101')
    api = SimpleNamespace(
        people=SimpleNamespace(details=lambda **_: person),
        licenses=SimpleNamespace(assign_licenses_to_users=lambda **_: (_ for _ in ()).throw(AssertionError('should not call api'))),
    )

    result = users_csv._apply_with_license_assignment(
        api,
        {'person_id': 'p-1', 'target_location_id': 'loc-1'},
        calling_license_id='lic-calling',
    )

    assert result['status'] == 'unchanged'
    assert result['reason'] == 'already_in_target_location'


def test_apply_with_license_assignment_skips_if_location_differs_only_by_base64_padding():
    person = SimpleNamespace(location_id='loc-1==', extension='6101')
    api = SimpleNamespace(
        people=SimpleNamespace(details=lambda **_: person),
        licenses=SimpleNamespace(assign_licenses_to_users=lambda **_: (_ for _ in ()).throw(AssertionError('should not call api'))),
    )

    result = users_csv._apply_with_license_assignment(
        api,
        {'person_id': 'p-1', 'target_location_id': 'loc-1'},
        calling_license_id='lic-calling',
    )

    assert result['status'] == 'unchanged'
    assert result['reason'] == 'already_in_target_location'


def test_apply_with_move_users_job_skips_if_location_differs_only_by_base64_padding():
    person = SimpleNamespace(location_id='loc-1', extension='6101')
    captured = {'called': False}

    def _should_not_call(**kwargs):
        captured['called'] = True
        raise AssertionError('should not call api')

    api = SimpleNamespace(
        telephony=SimpleNamespace(jobs=SimpleNamespace(move_users=SimpleNamespace(validate_or_initiate=_should_not_call))),
    )

    result = users_csv._apply_with_move_users_job(
        api,
        {'person_id': 'p-1', 'target_location_id': 'loc-1=='},
        person=person,
    )

    assert captured['called'] is False
    assert result['status'] == 'unchanged'
    assert result['reason'] == 'already_in_target_location'


def test_apply_with_license_assignment_uses_existing_extension():
    captured: dict[str, object] = {}
    person = SimpleNamespace(location_id='loc-old', extension='6101')

    def _assign(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(model_dump=lambda **__: {'ok': True})

    api = SimpleNamespace(
        people=SimpleNamespace(details=lambda **_: person),
        licenses=SimpleNamespace(assign_licenses_to_users=_assign),
    )

    users_csv._apply_with_license_assignment(
        api,
        {'person_id': 'p-1', 'target_location_id': 'loc-new'},
        calling_license_id='lic-calling',
    )

    req = captured['licenses'][0]
    assert req.properties.location_id == 'loc-new'
    assert req.properties.extension == '6101'


def test_run_script_supports_usuarios_remover_licencias(monkeypatch):
    def _fake_handler(token, person_id: str, remove_license_ids: list[str], org_id=None):
        return {'status': 'ok'}

    monkeypatch.setitem(launcher.HANDLERS, 'usuarios_remover_licencias', _fake_handler)

    result = launcher._run_script(
        script_name='usuarios_remover_licencias',
        parameter_map={
            'person_id': 'person-1',
            'remove_license_ids': 'lic-old-1,lic-old-2',
            'org_id': 'org-1',
        },
        token='tkn',
        auto_confirm=True,
        dry_run=True,
    )

    assert result['status'] == 'dry_run'
    assert result['params']['remove_license_ids'] == ['lic-old-1', 'lic-old-2']


def test_run_script_supports_usuarios_remover_licencias_alias_param(monkeypatch):
    def _fake_handler(token, person_id: str, remove_license_ids: list[str], org_id=None):
        return {'status': 'ok'}

    monkeypatch.setitem(launcher.HANDLERS, 'usuarios_remover_licencias', _fake_handler)

    result = launcher._run_script(
        script_name='usuarios_remover_licencias',
        parameter_map={
            'person_id': 'person-1',
            'remove_license_id': 'lic-old-1,lic-old-2',
            'org_id': 'org-1',
        },
        token='tkn',
        auto_confirm=True,
        dry_run=True,
    )

    assert result['status'] == 'dry_run'
    assert result['params']['remove_license_ids'] == ['lic-old-1', 'lic-old-2']
