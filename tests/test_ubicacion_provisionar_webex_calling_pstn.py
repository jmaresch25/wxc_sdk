from __future__ import annotations

from types import SimpleNamespace

import pytest

from Space_OdT.v21.transformacion.ubicacion_provisionar_webex_calling_pstn import (
    provisionar_ubicacion_webex_calling_pstn,
)
from wxc_sdk.rest import RestError


class _Model:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, **kwargs):
        return dict(self._payload)


class _Response404:
    status_code = 404
    text = '{"errorMessage":"missing"}'


def _fake_api(*, location=None, telephony_location_404=False, options=None, current=None):
    options = options or [_Model({'routeType': 'ROUTE_GROUP', 'routeId': 'rg-1'})]

    class LocationsApi:
        def __init__(self):
            self.created = False

        def by_name(self, name, org_id=None):
            return location

        def create(self, **kwargs):
            self.created = True
            return 'loc-created-id'

        def details(self, location_id, org_id=None):
            return _Model({'id': location_id, 'name': 'Nueva Sede'})

    class TelephonyLocationApi:
        def details(self, location_id, org_id=None):
            if telephony_location_404:
                raise RestError('not found', response=_Response404())
            return _Model({'id': location_id})

        def enable_for_calling(self, location, org_id=None):
            return 'loc-enabled-id'

    class PstnApi:
        def __init__(self):
            self.configure_called = False

        def list(self, location_id, org_id=None):
            return options

        def read(self, location_id, org_id=None):
            if current is None:
                raise RestError('not found', response=_Response404())
            return current

        def configure(self, **kwargs):
            self.configure_called = True

    return SimpleNamespace(
        locations=LocationsApi(),
        telephony=SimpleNamespace(location=TelephonyLocationApi(), pstn=PstnApi()),
    )


def test_provision_creates_location_enables_and_configures(monkeypatch):
    fake_api = _fake_api(location=None, telephony_location_404=True, current=None)
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.ubicacion_provisionar_webex_calling_pstn.create_api',
        lambda token: fake_api,
    )

    result = provisionar_ubicacion_webex_calling_pstn(
        token='tkn',
        location_name='Sede Norte',
        time_zone='Europe/Madrid',
        preferred_language='es_ES',
        announcement_language='es_ES',
        address1='Calle 1',
        city='Madrid',
        state='MD',
        postal_code='28001',
        country='ES',
        premise_route_type='ROUTE_GROUP',
        premise_route_id='rg-1',
    )

    assert result['status'] == 'success'
    assert result['created_location'] is True
    assert result['enabled_for_calling'] is True
    assert result['selected_route']['premise_route_id'] == 'rg-1'


def test_provision_noop_when_route_already_matches(monkeypatch):
    loc = _Model({'id': 'loc-1', 'name': 'Sede'})
    fake_api = _fake_api(
        location=loc,
        telephony_location_404=False,
        current=_Model({'routeType': 'ROUTE_GROUP', 'routeId': 'rg-1'}),
    )
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.ubicacion_provisionar_webex_calling_pstn.create_api',
        lambda token: fake_api,
    )

    result = provisionar_ubicacion_webex_calling_pstn(
        token='tkn',
        location_name='Sede',
        time_zone='Europe/Madrid',
        preferred_language='es_ES',
        announcement_language='es_ES',
        address1='Calle 1',
        city='Madrid',
        state='MD',
        postal_code='28001',
        country='ES',
        premise_route_type='ROUTE_GROUP',
        premise_route_id='rg-1',
    )

    assert result['status'] == 'success'
    assert 'ya tenía la ruta PSTN' in result['message']


def test_provision_fails_if_requested_route_not_available(monkeypatch):
    loc = _Model({'id': 'loc-1', 'name': 'Sede'})
    fake_api = _fake_api(
        location=loc,
        telephony_location_404=False,
        options=[_Model({'routeType': 'TRUNK', 'routeId': 'trunk-1'})],
        current=None,
    )
    monkeypatch.setattr(
        'Space_OdT.v21.transformacion.ubicacion_provisionar_webex_calling_pstn.create_api',
        lambda token: fake_api,
    )

    with pytest.raises(ValueError, match='no está disponible en connectionOptions'):
        provisionar_ubicacion_webex_calling_pstn(
            token='tkn',
            location_name='Sede',
            time_zone='Europe/Madrid',
            preferred_language='es_ES',
            announcement_language='es_ES',
            address1='Calle 1',
            city='Madrid',
            state='MD',
            postal_code='28001',
            country='ES',
            premise_route_type='ROUTE_GROUP',
            premise_route_id='rg-x',
        )
