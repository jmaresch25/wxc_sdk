from argparse import Namespace

from actions.action_alta_sedes_wbxc import build_headers, build_payload


def test_build_payload_uses_required_location_fields():
    args = Namespace(
        name="Denver",
        time_zone="America/Chicago",
        preferred_language="en_us",
        announcement_language="fr_fr",
        address1="771 Alder Drive",
        city="Milpitas",
        state="CA",
        postal_code="95035",
        country="US",
    )

    payload = build_payload(args)

    assert payload == {
        "name": "Denver",
        "timeZone": "America/Chicago",
        "preferredLanguage": "en_us",
        "announcementLanguage": "fr_fr",
        "address": {
            "address1": "771 Alder Drive",
            "city": "Milpitas",
            "state": "CA",
            "postalCode": "95035",
            "country": "US",
        },
    }


def test_build_headers_use_bearer_token_auth():
    headers = build_headers("abc123")

    assert headers["Authorization"] == "Bearer abc123"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
