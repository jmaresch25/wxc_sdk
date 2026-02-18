from __future__ import annotations

from types import SimpleNamespace

from Space_OdT.v21.transformacion.launcher_tester_api_remota import _execute_actions
from Space_OdT.v21.transformacion.ubicacion_configurar_llamadas_internas import configurar_llamadas_internas_ubicacion
from Space_OdT.v21.transformacion.ubicacion_configurar_permisos_salientes_defecto import (
    configurar_permisos_salientes_defecto_ubicacion,
)
from Space_OdT.v21.transformacion.usuarios_alta_people import alta_usuario_people

from Space_OdT.v21.transformacion.usuarios_alta_scim import alta_usuario_scim
from Space_OdT.v21.transformacion.usuarios_anadir_intercom_legacy import anadir_intercom_legacy_usuario
from Space_OdT.v21.transformacion.usuarios_modificar_licencias import modificar_licencias_usuario


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



def test_usuarios_alta_scim_creates_or_skips(monkeypatch):
    class ScimUsersApi:
        def __init__(self):
            self.created = None
            self.resources = []

        def search(self, org_id, filter, count=1):
            return SimpleNamespace(resources=self.resources)

        def create(self, org_id, user):
            self.created = (org_id, user)
            return _Model({'id': 'scim-1', 'userName': user.user_name})

    users_api = ScimUsersApi()
    fake_api = SimpleNamespace(scim=SimpleNamespace(users=users_api))
    monkeypatch.setattr('Space_OdT.v21.transformacion.usuarios_alta_scim.create_api', lambda token: fake_api)

    created = alta_usuario_scim(
        token='tkn',
        org_id='org1',
        email='scim@example.com',
        first_name='Scim',
        last_name='User',
    )
    assert created['status'] == 'success'
    assert users_api.created[0] == 'org1'

    users_api.resources = [_Model({'id': 'exists'})]
    skipped = alta_usuario_scim(
        token='tkn',
        org_id='org1',
        email='scim@example.com',
        first_name='Scim',
        last_name='User',
    )
    assert skipped['status'] == 'skipped'


def test_usuarios_modificar_licencias_calls_assign(monkeypatch):
    class LicensesApi:
        def __init__(self):
            self.last = None

        def assign_licenses_to_users(self, person_id=None, licenses=None, org_id=None):
            self.last = (person_id, licenses, org_id)
            return _Model({'personId': person_id, 'licenses': ['l1']})

    licenses = LicensesApi()
    fake_api = SimpleNamespace(licenses=licenses)
    monkeypatch.setattr('Space_OdT.v21.transformacion.usuarios_modificar_licencias.create_api', lambda token: fake_api)

    result = modificar_licencias_usuario(
        token='tkn',
        person_id='person-1',
        add_license_ids=['lic-a'],
        org_id='org1',
    )

    assert result['status'] == 'success'
    assert licenses.last[0] == 'person-1'


def test_usuarios_anadir_intercom_legacy_updates_or_skips(monkeypatch):
    class NumbersApi:
        def __init__(self):
            self.last_update = None
            self._existing = []

        def read(self, person_id, org_id=None):
            return _Model({'distinctiveRingEnabled': False, 'phoneNumbers': list(self._existing)})

        def update(self, person_id, update, org_id=None):
            self.last_update = (person_id, update, org_id)

    numbers = NumbersApi()
    fake_api = SimpleNamespace(person_settings=SimpleNamespace(numbers=numbers))
    monkeypatch.setattr('Space_OdT.v21.transformacion.usuarios_anadir_intercom_legacy.create_api', lambda token: fake_api)

    updated = anadir_intercom_legacy_usuario(
        token='tkn',
        person_id='person-1',
        legacy_phone_number='+34910000099',
    )
    assert updated['status'] == 'success'
    assert numbers.last_update[0] == 'person-1'

    numbers._existing = [{'directNumber': '+34910000099'}]
    skipped = anadir_intercom_legacy_usuario(
        token='tkn',
        person_id='person-1',
        legacy_phone_number='+34910000099',
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
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.launcher_tester_api_remota.modificar_licencias_usuario',
        lambda token, **kwargs: {'status': 'success', 'kind': 'licenses'},
    )

    payload = {
        'acciones': [
            {'action': 'ubicacion_configurar_llamadas_internas', 'params': {'location_id': 'loc1', 'enable_unknown_extension_route_policy': False}},
            {'action': 'usuarios_modificar_licencias', 'params': {'person_id': 'p1', 'add_license_ids': ['lic-a']}},
            {'action': 'desconocida', 'params': {}},
        ]
    }

    report = _execute_actions(token='tkn', payload=payload)

    assert report['results'][0]['result']['kind'] == 'internal'
    assert report['results'][1]['result']['kind'] == 'licenses'
    assert report['results'][2]['status'] == 'rejected'


def test_launcher_tester_api_remota_supports_first_three_location_actions(monkeypatch):
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.launcher_tester_api_remota.configurar_pstn_ubicacion',
        lambda token, **kwargs: {'status': 'success', 'kind': 'pstn'},
    )
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.launcher_tester_api_remota.alta_numeraciones_desactivadas',
        lambda token, **kwargs: {'status': 'success', 'kind': 'numbers'},
    )
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.launcher_tester_api_remota.actualizar_cabecera_ubicacion',
        lambda token, **kwargs: {'status': 'success', 'kind': 'header'},
    )

    payload = {
        'acciones': [
            {
                'action': 'ubicacion_configurar_pstn',
                'params': {
                    'location_id': 'loc1',
                    'premise_route_type': 'ROUTE_GROUP',
                    'premise_route_id': 'rg1',
                },
            },
            {
                'action': 'ubicacion_alta_numeraciones_desactivadas',
                'params': {
                    'location_id': 'loc1',
                    'phone_numbers': ['+34910000001'],
                },
            },
            {
                'action': 'ubicacion_actualizar_cabecera',
                'params': {
                    'location_id': 'loc1',
                    'phone_number': '+34910000001',
                },
            },
        ]
    }

    report = _execute_actions(token='tkn', payload=payload)

    assert report['results'][0]['result']['kind'] == 'pstn'
    assert report['results'][1]['result']['kind'] == 'numbers'
    assert report['results'][2]['result']['kind'] == 'header'


def test_configurar_perfil_saliente_custom_workspace_uses_report_json(monkeypatch):
    from Space_OdT.v21.transformacion.workspaces_configurar_perfil_saliente_custom import (
        configurar_perfil_saliente_custom_workspace,
    )

    class PermissionsOutApi:
        def __init__(self):
            self.last = None

        def configure(self, entity_id, settings, org_id=None):
            self.last = (entity_id, settings, org_id)

    permissions = PermissionsOutApi()
    fake_api = SimpleNamespace(workspace_settings=SimpleNamespace(permissions_out=permissions))

    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.workspaces_configurar_perfil_saliente_custom.create_api',
        lambda token: fake_api,
    )
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.workspaces_configurar_perfil_saliente_custom.load_report_json',
        lambda filename: {
            'useCustomEnabled': False,
            'useCustomPermissions': True,
            'callingPermissions': [{'callType': 'INTERNAL_CALL', 'action': 'ALLOW', 'transferEnabled': True}],
        },
    )

    result = configurar_perfil_saliente_custom_workspace(token='tkn', workspace_id='ws1')

    assert result['status'] == 'success'
    assert permissions.last[0] == 'ws1'
    assert permissions.last[1].use_custom_enabled is False


def test_configurar_permisos_salientes_defecto_ubicacion_uses_report_json(monkeypatch):
    class PermissionsOutApi:
        def __init__(self):
            self.last = None

        def configure(self, entity_id, settings, org_id=None):
            self.last = (entity_id, settings, org_id)

    permissions = PermissionsOutApi()
    fake_api = SimpleNamespace(telephony=SimpleNamespace(location=SimpleNamespace(permissions_out=permissions)))

    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.ubicacion_configurar_permisos_salientes_defecto.create_api',
        lambda token: fake_api,
    )
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.ubicacion_configurar_permisos_salientes_defecto.load_report_json',
        lambda filename: {
            'callingPermissions': [{'callType': 'INTERNAL', 'action': 'ALLOW', 'transferEnabled': True}],
        },
    )

    result = configurar_permisos_salientes_defecto_ubicacion(token='tkn', location_id='loc1')

    assert result['status'] == 'success'
    assert permissions.last[0] == 'loc1'
    assert permissions.last[1].calling_permissions.internal.action == 'ALLOW'
