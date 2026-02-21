from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from Space_OdT.v21.transformacion.ubicacion_actualizar_cabecera import actualizar_cabecera_ubicacion
from Space_OdT.v21.transformacion.ubicacion_alta_numeraciones_desactivadas import alta_numeraciones_desactivadas
from Space_OdT.v21.transformacion.ubicacion_configurar_pstn import configurar_pstn_ubicacion
from Space_OdT.v21.transformacion.usuarios_alta_people import alta_usuario_people


class _Model:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, **kwargs):
        return dict(self._payload)


def test_configurar_pstn_ubicacion_uses_sdk_calls(monkeypatch):
    calls = []

    class Pstn:
        def read(self, location_id, org_id=None):
            calls.append(('read', location_id, org_id))
            return _Model({'id': 'rg-old'})

        def list(self, location_id, org_id=None):
            calls.append(('list', location_id, org_id))
            return [_Model({'id': 'rg-new', 'pstn_connection_type': 'LOCAL_GATEWAY'})]

        def configure(self, **kwargs):
            calls.append(('configure', kwargs))

    fake_api = SimpleNamespace(telephony=SimpleNamespace(pstn=Pstn()))
    monkeypatch.setattr('Space_OdT.v21.transformacion.ubicacion_configurar_pstn.create_api', lambda token: fake_api)
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.ubicacion_configurar_pstn._enable_location_for_calling',
        lambda **kwargs: {'status': 'already_enabled'},
    )

    result = configurar_pstn_ubicacion(
        token='tkn',
        location_id='loc1',
        premise_route_type='ROUTE_GROUP',
        premise_route_id='rg-new',
        org_id='org1',
    )

    assert result['status'] == 'success'
    configure_calls = [call for call in calls if call[0] == 'configure']
    assert configure_calls
    assert configure_calls[0][1]['id'] == 'rg-new'


def test_alta_numeraciones_desactivadas_calls_number_add(monkeypatch):
    class NumberApi:
        def __init__(self):
            self.last_kwargs = None

        def add(self, **kwargs):
            self.last_kwargs = kwargs
            return _Model({'errors': []})

    number_api = NumberApi()

    class LocationApi:
        def __init__(self):
            self.number = number_api

        def phone_numbers(self, location_id, org_id=None):
            return [_Model({'phoneNumber': '+34910000000'})]

    fake_api = SimpleNamespace(telephony=SimpleNamespace(location=LocationApi()))
    monkeypatch.setattr('Space_OdT.v21.transformacion.ubicacion_alta_numeraciones_desactivadas.create_api', lambda token: fake_api)

    result = alta_numeraciones_desactivadas(token='tkn', location_id='loc1', phone_numbers=['+34919999999'])

    assert result['status'] == 'success'
    assert number_api.last_kwargs['location_id'] == 'loc1'
    assert number_api.last_kwargs['phone_numbers'] == ['+34919999999']


def test_actualizar_cabecera_ubicacion_updates_calling_line(monkeypatch):
    captured = {}

    class LocationApi:
        def update(self, location_id, settings, org_id=None):
            captured['location_id'] = location_id
            captured['settings'] = settings
            captured['org_id'] = org_id
            return 'batch-1'

    fake_api = SimpleNamespace(telephony=SimpleNamespace(location=LocationApi()))
    monkeypatch.setattr('Space_OdT.v21.transformacion.ubicacion_actualizar_cabecera.create_api', lambda token: fake_api)

    result = actualizar_cabecera_ubicacion(
        token='tkn',
        location_id='loc1',
        phone_number='+34918887777',
        calling_line_name='Cabecera Central',
    )

    assert result['status'] == 'success'
    assert captured['location_id'] == 'loc1'
    assert captured['settings'].calling_line_id.phone_number == '+34918887777'
    assert captured['settings'].calling_line_id.name == 'Cabecera Central'


def test_actualizar_cabecera_ubicacion_requires_mandatory_params():
    with pytest.raises(ValueError, match='location_id es obligatorio'):
        actualizar_cabecera_ubicacion(token='tkn', location_id='', phone_number='+34918887777')

    with pytest.raises(ValueError, match='phone_number es obligatorio'):
        actualizar_cabecera_ubicacion(token='tkn', location_id='loc1', phone_number='')


def test_configurar_pstn_rejects_invalid_route_type():
    with pytest.raises(ValueError):
        configurar_pstn_ubicacion(
            token='tkn',
            location_id='loc1',
            premise_route_type='INVALID',
            premise_route_id='rg',
        )


def test_configurar_pstn_requires_local_gateway_option(monkeypatch):
    class Pstn:
        def list(self, location_id, org_id=None):
            return [_Model({'id': 'ccp-1', 'pstn_connection_type': 'INTEGRATED_CCP'})]

    fake_api = SimpleNamespace(telephony=SimpleNamespace(pstn=Pstn()))
    monkeypatch.setattr('Space_OdT.v21.transformacion.ubicacion_configurar_pstn.create_api', lambda token: fake_api)
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.ubicacion_configurar_pstn._enable_location_for_calling',
        lambda **kwargs: {'status': 'already_enabled'},
    )

    with pytest.raises(ValueError, match='LOCAL_GATEWAY'):
        configurar_pstn_ubicacion(
            token='tkn',
            location_id='loc1',
            premise_route_type='ROUTE_GROUP',
            premise_route_id='rg',
        )



def test_configurar_pstn_accepts_display_name_selector(monkeypatch):
    calls = []

    class Pstn:
        def list(self, location_id, org_id=None):
            return [_Model({'id': 'prem-1', 'displayName': 'Premises-based PSTN'})]

        def configure(self, **kwargs):
            calls.append(kwargs)

    fake_api = SimpleNamespace(telephony=SimpleNamespace(pstn=Pstn()))
    monkeypatch.setattr('Space_OdT.v21.transformacion.ubicacion_configurar_pstn.create_api', lambda token: fake_api)
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.ubicacion_configurar_pstn._enable_location_for_calling',
        lambda **kwargs: {'status': 'already_enabled'},
    )

    result = configurar_pstn_ubicacion(
        token='tkn',
        location_id='loc1',
        premise_route_type='ROUTE_GROUP',
        premise_route_id='rg-new',
        pstn_connection_type='LOCAL_GATEWAY',
    )

    assert result['status'] == 'success'
    assert calls[0]['id'] == 'prem-1'

def test_alta_usuario_people_normalizes_string_licenses(monkeypatch):
    captured = {}

    class PeopleApi:
        def list(self, email, org_id=None):
            return []

        def create(self, settings, calling_data=True):
            captured['licenses'] = settings.licenses
            return _Model({'id': 'person-1'})

    fake_api = SimpleNamespace(people=PeopleApi())
    monkeypatch.setattr('Space_OdT.v21.transformacion.usuarios_alta_people.create_api', lambda token: fake_api)

    result = alta_usuario_people(
        token='tkn',
        email='zulema@example.com',
        first_name='Zulema',
        last_name='Tal',
        licenses='Webex Calling Professional',
    )

    assert result['status'] == 'success'
    assert captured['licenses'] == ['Webex Calling Professional']


def test_alta_usuario_people_normalizes_csv_string_licenses(monkeypatch):
    captured = {}

    class PeopleApi:
        def list(self, email, org_id=None):
            return []

        def create(self, settings, calling_data=True):
            captured['licenses'] = settings.licenses
            return _Model({'id': 'person-2'})

    fake_api = SimpleNamespace(people=PeopleApi())
    monkeypatch.setattr('Space_OdT.v21.transformacion.usuarios_alta_people.create_api', lambda token: fake_api)

    alta_usuario_people(
        token='tkn',
        email='zulema@example.com',
        first_name='Zulema',
        last_name='Tal',
        licenses=' lic-a, lic-b ',
    )

    assert captured['licenses'] == ['lic-a', 'lic-b']



from argparse import Namespace
from Space_OdT.v21.transformacion import common as transform_common


def test_apply_standalone_input_arguments_uses_repo_input_data_default(tmp_path, monkeypatch):
    args = Namespace(csv=None, input_dir=None, location_id='loc-cli', phone_numbers=['+341'])
    seen = {}

    def fake_find_csv(input_dir, expected_name):
        seen['input_dir'] = input_dir
        if expected_name == 'Global.csv':
            return tmp_path / 'Global.csv'
        return tmp_path / 'Ubicaciones.csv'

    monkeypatch.setattr(transform_common, '_find_csv_case_insensitive', fake_find_csv)
    monkeypatch.setattr(transform_common, '_first_csv_row', lambda path: {'location_id': 'loc-csv', 'phone_numbers': '+3491'})

    resolved = transform_common.apply_standalone_input_arguments(
        args,
        required=['location_id', 'phone_numbers'],
        list_fields=['phone_numbers'],
        domain_csv_name='Ubicaciones.csv',
        script_name='test_script',
    )

    expected = Path(transform_common.__file__).resolve().parents[3] / 'input_data'
    assert Path(resolved.input_dir) == expected
    assert seen['input_dir'] == expected
    assert resolved.location_id == 'loc-cli'
    assert resolved.phone_numbers == ['+341']


def test_apply_standalone_input_arguments_merges_domain_and_global(tmp_path):
    input_dir = tmp_path / 'input_data'
    input_dir.mkdir()
    (input_dir / 'Global.csv').write_text('email,first_name,last_name,licenses\nfrom_global@example.com,Global,Fallback,"lic-a|lic-b"\n', encoding='utf-8')
    (input_dir / 'Usuarios.csv').write_text('email,first_name,last_name\nfrom_domain@example.com,Domain,User\n', encoding='utf-8')

    args = Namespace(csv=None, input_dir=str(input_dir), email=None, first_name=None, last_name=None, licenses=None)
    resolved = transform_common.apply_standalone_input_arguments(
        args,
        required=['email', 'first_name', 'last_name'],
        list_fields=['licenses'],
        domain_csv_name='Usuarios.csv',
        script_name='test_script',
    )

    assert resolved.email == 'from_domain@example.com'
    assert resolved.first_name == 'Domain'
    assert resolved.last_name == 'User'
    assert resolved.licenses == ['lic-a', 'lic-b']
