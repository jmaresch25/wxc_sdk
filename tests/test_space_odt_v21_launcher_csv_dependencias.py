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


def test_apply_with_move_users_job_skips_if_user_already_in_target_location():
    person = SimpleNamespace(location_id='loc-1', extension='6101')
    api = SimpleNamespace(
        telephony=SimpleNamespace(
            jobs=SimpleNamespace(
                move_users=SimpleNamespace(validate_or_initiate=lambda **_: (_ for _ in ()).throw(AssertionError('should not call api')))
            )
        )
    )

    result = users_csv._apply_with_move_users_job(
        api,
        {'person_id': 'p-1', 'target_location_id': 'loc-1'},
        person=person,
    )

    assert result['status'] == 'unchanged'
    assert result['reason'] == 'already_in_target_location'


def test_apply_with_move_users_job_uses_existing_extension():
    captured: dict[str, object] = {}
    person = SimpleNamespace(location_id='loc-old', extension='6101')

    def _move_validate_or_initiate(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(model_dump=lambda **__: {'ok': True})

    api = SimpleNamespace(
        telephony=SimpleNamespace(
            jobs=SimpleNamespace(
                move_users=SimpleNamespace(validate_or_initiate=_move_validate_or_initiate)
            )
        )
    )

    result = users_csv._apply_with_move_users_job(
        api,
        {'person_id': 'p-1', 'target_location_id': 'loc-new'},
        person=person,
    )

    users_list = captured['users_list']
    assert users_list[0].location_id == 'loc-new'
    assert users_list[0].users[0].extension == '6101'
    assert result['path'] == 'telephony.jobs.move_users.validate_or_initiate'


def test_normalize_location_id_ignores_base64_padding():
    assert users_csv._normalize_location_id('abc==') == 'abc'
    assert users_csv._normalize_location_id('abc') == 'abc'


def test_apply_location_change_for_calling_user_uses_move_users_job(monkeypatch):
    person = SimpleNamespace(location_id='loc-a', extension='6101')
    monkeypatch.setattr(users_csv, '_is_calling_user', lambda _: True)
    monkeypatch.setattr(users_csv, '_apply_with_move_users_job', lambda api, row, person: {'status': 'updated', 'path': 'telephony.jobs.move_users.validate_or_initiate'})

    api = SimpleNamespace(people=SimpleNamespace(details=lambda **_: person))
    result = users_csv._apply_location_change(api, {'person_id': 'p-1', 'target_location_id': 'loc-b'})

    assert result['path'] == 'telephony.jobs.move_users.validate_or_initiate'


def test_assign_users_to_locations_applies_all_rows(monkeypatch, tmp_path):
    csv_path = tmp_path / 'people_to_location.csv'
    csv_path.write_text(
        'selected,person_id,target_location_id\n1,p-1,loc-1\n1,p-2,loc-1\n',
        encoding='utf-8',
    )

    monkeypatch.setattr(users_csv, 'load_runtime_env', lambda: None)
    monkeypatch.setattr(users_csv, 'get_token', lambda token: token or 'tkn')

    def _apply(api, row):
        return {'person_id': row['person_id'], 'status': 'updated'}

    logs: list[tuple[str, dict[str, object]]] = []

    def _logger(_name):
        return lambda event, payload: logs.append((event, payload))

    monkeypatch.setattr(users_csv, 'action_logger', _logger)
    monkeypatch.setattr(users_csv, '_apply_location_change', _apply)
    monkeypatch.setattr(users_csv, 'create_api', lambda _token: object())

    results = users_csv.assign_users_to_locations(csv_path=csv_path, token='tkn', dry_run=False)

    assert len(results) == 2
    assert results[0]['status'] == 'updated'
    assert results[1]['status'] == 'updated'
    assert logs[0][0] == 'user_location_updated'
    assert logs[1][0] == 'user_location_updated'
