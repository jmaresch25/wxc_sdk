from __future__ import annotations

from types import SimpleNamespace

from Space_OdT.v21.transformacion.usuarios_modificar_licencias import modificar_licencias_usuario


class _Model:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, **kwargs):
        return self._payload


def test_modificar_licencias_skips_remove_when_license_not_assigned(monkeypatch):
    class LicensesApi:
        def __init__(self):
            self.last = None

        def assign_licenses_to_users(self, person_id=None, licenses=None, org_id=None):
            self.last = (person_id, licenses, org_id)
            return _Model({'personId': person_id})

    class PeopleApi:
        def details(self, person_id=None, calling_data=None, org_id=None):
            return SimpleNamespace(licenses=['lic-actual'])

    licenses = LicensesApi()
    fake_api = SimpleNamespace(licenses=licenses, people=PeopleApi())
    monkeypatch.setattr('Space_OdT.v21.transformacion.usuarios_modificar_licencias.create_api', lambda token: fake_api)

    result = modificar_licencias_usuario(
        token='tkn',
        person_id='person-1',
        remove_license_ids=['lic-no-asignada'],
        org_id='org1',
    )

    assert result['status'] == 'skipped'
    assert result['reason'] == 'remove_license_ids_not_assigned'
    assert result['skipped_remove_license_ids'] == ['lic-no-asignada']
    assert licenses.last is None
