from urllib.parse import quote

from wxc_sdk.telephony.autoattendant import AutoAttendantApi


class DummySession:
    def ep(self, path: str = None):
        path = path and f'/{path}' or ''
        return f'https://webexapis.com/v1{path}'


def test_endpoint_encodes_location_and_auto_attendant_ids():
    api = AutoAttendantApi(session=DummySession())

    location_id = 'ciscospark://us/LOCATION/4ffd8bf3-de31-4412-8dda-b4424b119b48'
    auto_attendant_id = 'ciscospark://us/AUTO_ATTENDANT/abc'

    endpoint = api._endpoint(location_id=location_id, auto_attendant_id=auto_attendant_id)

    assert endpoint == (
        'https://webexapis.com/v1/telephony/config/locations/'
        f'{quote(location_id, safe="")}/autoAttendants/{quote(auto_attendant_id, safe="")}'
    )
