from __future__ import annotations

import argparse
from typing import Any

from wxc_sdk.person_settings.permissions_out import OutgoingPermissions

from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'ubicacion_configurar_permisos_salientes_defecto'


def configurar_permisos_salientes_defecto_ubicacion(
    *,
    token: str,
    location_id: str,
    org_id: str | None = None,
) -> dict[str, Any]:
    """
    Restablece permisos salientes de ubicación para usar configuración por defecto.
    """
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    before = model_to_dict(api.telephony.location.permissions_out.read(entity_id=location_id, org_id=org_id))
    settings = OutgoingPermissions(use_custom_enabled=False, use_custom_permissions=False)
    request = {
        'entity_id': location_id,
        'settings': model_to_dict(settings),
        'org_id': org_id,
    }

    log('before_read', {'before': before})
    log('configure_request', request)

    api.telephony.location.permissions_out.configure(entity_id=location_id, settings=settings, org_id=org_id)
    after = model_to_dict(api.telephony.location.permissions_out.read(entity_id=location_id, org_id=org_id))

    result = {'status': 'success', 'api_response': {'before': before, 'after': after, 'request': request}}
    log('configure_response', result)
    return result


def main() -> None:
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Configurar permisos salientes por defecto en una ubicación')
    parser.add_argument('--token', default=None)
    parser.add_argument('--location-id', required=True)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()

    payload = configurar_permisos_salientes_defecto_ubicacion(
        token=get_token(args.token),
        location_id=args.location_id,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
