from __future__ import annotations

from types import SimpleNamespace

from Space_OdT.v21.transformacion.launcher_tester_api_remota import _execute_actions
from Space_OdT.v21.transformacion.ubicacion_configurar_llamadas_internas import configurar_llamadas_internas_ubicacion
from Space_OdT.v21.transformacion.ubicacion_configurar_permisos_salientes_defecto import (
    configurar_permisos_salientes_defecto_ubicacion,
)
from Space_OdT.v21.transformacion.usuarios_alta_people import alta_usuario_people


class _Model:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, **kwargs):
        return dict(self._payload)


def test_configurar_llamadas_internas_ubicacion_updates_settings(monkeypatch):
    class InternalDialing:
        def __init__(self):
            self.enable_unknown_extension_route_policy = False
            self.unknown_extension_route_identity = None

        def model_dump(self, **kwargs):
            return {
                'enableUnknownExtensionRoutePolicy': self.enable_unknown_extension_route_policy,
                'unknownExtensionRouteIdentity': self.unknown_extension_route_identity and {
                    'routeId': self.unknown_extension_route_identity.route_id,
                    'routeType': self.unknown_extension_route_identity.route_type,
                },
            }

    settings = InternalDialing()

    class InternalDialingApi:
        def read(self, location_id, org_id=None):
            return settings

        def update(self, location_id, update, org_id=None):
            settings.enable_unknown_extension_route_policy = update.enable_unknown_extension_route_policy
            settings.unknown_extension_route_identity = update.unknown_extension_route_identity

    fake_api = SimpleNamespace(telephony=SimpleNamespace(location=SimpleNamespace(internal_dialing=InternalDialingApi())))
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.ubicacion_configurar_llamadas_internas.create_api',
        lambda token: fake_api,
    )

    result = configurar_llamadas_internas_ubicacion(
        token='tkn',
        location_id='loc1',
        enable_unknown_extension_route_policy=True,
        premise_route_id='rg-1',
        premise_route_type='ROUTE_GROUP',
    )

    assert result['status'] == 'success'
    assert settings.enable_unknown_extension_route_policy is True
    assert settings.unknown_extension_route_identity.route_id == 'rg-1'


def test_configurar_permisos_salientes_defecto_ubicacion_calls_configure(monkeypatch):
    class PermissionsOutApi:
        def __init__(self):
            self.last = None

        def read(self, entity_id, org_id=None):
            return _Model({'useCustomEnabled': True})

        def configure(self, entity_id, settings, org_id=None):
            self.last = (entity_id, settings)

    permissions = PermissionsOutApi()
    fake_api = SimpleNamespace(telephony=SimpleNamespace(location=SimpleNamespace(permissions_out=permissions)))

    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.ubicacion_configurar_permisos_salientes_defecto.create_api',
        lambda token: fake_api,
    )

    result = configurar_permisos_salientes_defecto_ubicacion(token='tkn', location_id='loc1')

    assert result['status'] == 'success'
    assert permissions.last[0] == 'loc1'


def test_usuarios_alta_people_creates_or_skips(monkeypatch):
    class PeopleApi:
        def __init__(self):
            self.created = None
            self._existing = []

        def list(self, email, org_id=None):
            return self._existing

        def create(self, settings, calling_data=False):
            self.created = settings
            return _Model({'id': 'person-1', 'emails': settings.emails})

    people = PeopleApi()
    fake_api = SimpleNamespace(people=people)
    monkeypatch.setattr('Space_OdT.v21.transformacion.usuarios_alta_people.create_api', lambda token: fake_api)

    created = alta_usuario_people(
        token='tkn',
        email='john@example.com',
        first_name='John',
        last_name='Doe',
    )
    assert created['status'] == 'success'
    assert people.created is not None

    people._existing = [_Model({'id': 'already'})]
    skipped = alta_usuario_people(
        token='tkn',
        email='john@example.com',
        first_name='John',
        last_name='Doe',
    )
    assert skipped['status'] == 'skipped'


def test_launcher_tester_api_remota_executes_supported_and_rejects_unknown(monkeypatch):
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.launcher_tester_api_remota.configurar_llamadas_internas_ubicacion',
        lambda token, **kwargs: {'status': 'success', 'kind': 'internal'},
    )
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.launcher_tester_api_remota.configurar_permisos_salientes_defecto_ubicacion',
        lambda token, **kwargs: {'status': 'success', 'kind': 'permissions'},
    )

    payload = {
        'acciones': [
            {'action': 'ubicacion_configurar_llamadas_internas', 'params': {'location_id': 'loc1', 'enable_unknown_extension_route_policy': False}},
            {'action': 'desconocida', 'params': {}},
        ]
    }

    report = _execute_actions(token='tkn', payload=payload)

    assert report['results'][0]['result']['kind'] == 'internal'
    assert report['results'][1]['status'] == 'rejected'
