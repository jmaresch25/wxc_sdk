from __future__ import annotations

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

    with pytest.raises(ValueError, match='LOCAL_GATEWAY'):
        configurar_pstn_ubicacion(
            token='tkn',
            location_id='loc1',
            premise_route_type='ROUTE_GROUP',
            premise_route_id='rg',
        )

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

