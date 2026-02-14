from __future__ import annotations

import argparse
from typing import Any

from wxc_sdk.person_settings.numbers import UpdatePersonNumbers, UpdatePersonPhoneNumber

from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'usuarios_anadir_intercom_legacy'


def anadir_intercom_legacy_usuario(
    *,
    token: str,
    person_id: str,
    legacy_phone_number: str,
    org_id: str | None = None,
) -> dict[str, Any]:
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    before = api.person_settings.numbers.read(person_id=person_id, org_id=org_id)
    before_payload = model_to_dict(before)
    already_exists = any((num.get('directNumber') == legacy_phone_number) for num in before_payload.get('phoneNumbers', []))
    if already_exists:
        result = {
            'status': 'skipped',
            'reason': 'legacy_number_already_present',
            'api_response': {'before': before_payload},
        }
        log('update_skipped', {'person_id': person_id, 'legacy_phone_number': legacy_phone_number})
        return result

    update = UpdatePersonNumbers(
        phone_numbers=[UpdatePersonPhoneNumber(action='ADD', external=legacy_phone_number, primary=False)],
        enable_distinctive_ring_pattern=bool(before_payload.get('distinctiveRingEnabled', False)),
    )
    request = {'person_id': person_id, 'org_id': org_id, 'update': model_to_dict(update)}
    log('update_request', request)

    api.person_settings.numbers.update(person_id=person_id, update=update, org_id=org_id)
    after = api.person_settings.numbers.read(person_id=person_id, org_id=org_id)
    after_payload = model_to_dict(after)

    result = {
        'status': 'success',
        'api_response': {'request': request, 'before': before_payload, 'after': after_payload},
    }
    log('update_response', result)
    return result


def main() -> None:
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Añadir intercom legacy (número secundario) a usuario')
    parser.add_argument('--token', default=None)
    parser.add_argument('--person-id', required=True)
    parser.add_argument('--legacy-phone-number', required=True)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()

    payload = anadir_intercom_legacy_usuario(
        token=get_token(args.token),
        person_id=args.person_id,
        legacy_phone_number=args.legacy_phone_number,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
