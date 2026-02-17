from __future__ import annotations

from types import SimpleNamespace

from Space_OdT.v21.transformacion.workspaces_configurar_desvio_prefijo53_telephony import (
    configurar_desvio_prefijo53_workspace_telephony,
)


class _Session:
    def __init__(self):
        self.last_put = None

    def ep(self, path: str) -> str:
        return f'https://example.test/v1/{path}'

    def rest_get(self, *, url: str, params=None):
        return {'url': url, 'params': params, 'enabled': False}

    def rest_put(self, *, url: str, params=None, json=None):
        self.last_put = {'url': url, 'params': params, 'json': json}


class _AvailableNumbers:
    def __init__(self, numbers: list[str]):
        self._numbers = numbers

    def call_forward(self, *, entity_id: str, phone_number: list[str] = None, org_id: str = None):
        return [SimpleNamespace(phone_number=n) for n in self._numbers]


def _fake_api(available_numbers: list[str] | None = None):
    session = _Session()
    available_api = _AvailableNumbers(available_numbers or [])
    return SimpleNamespace(
        session=session,
        workspace_settings=SimpleNamespace(available_numbers=available_api),
    )


def test_configure_workspace_forwarding_telephony_uses_rest_put(monkeypatch):
    api = _fake_api()
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.workspaces_configurar_desvio_prefijo53_telephony.create_api',
        lambda token: api,
    )

    result = configurar_desvio_prefijo53_workspace_telephony(
        token='tkn',
        workspace_id='workspace-1',
        extension='5102',
        destination='539402744',
        org_id='org-1',
    )

    assert result['status'] == 'success'
    assert api.session.last_put['url'].endswith('/telephony/config/workspaces/workspace-1/callForwarding')
    assert api.session.last_put['params'] == {'orgId': 'org-1'}
    assert api.session.last_put['json']['enabled'] is True
    assert api.session.last_put['json']['destination'] == '539402744'


def test_configure_workspace_forwarding_telephony_rejects_unavailable_destination(monkeypatch):
    api = _fake_api(available_numbers=['531111'])
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.workspaces_configurar_desvio_prefijo53_telephony.create_api',
        lambda token: api,
    )

    result = configurar_desvio_prefijo53_workspace_telephony(
        token='tkn',
        workspace_id='workspace-1',
        extension='5102',
        destination='539402744',
        validate_destination=True,
    )

    assert result['status'] == 'rejected'
    assert result['reason'] == 'destination_not_available_for_call_forwarding'
    assert api.session.last_put is None
