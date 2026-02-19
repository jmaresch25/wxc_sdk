from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
import base64
from typing import Any

from wxc_sdk.base import webex_id_to_uuid
from wxc_sdk.person_settings.permissions_out import OutgoingPermissions

from .common import (
    action_logger,
    apply_csv_arguments,
    create_api,
    get_token,
    load_report_json,
    load_runtime_env,
    model_to_dict,
)

SCRIPT_NAME = 'ubicacion_configurar_permisos_salientes_defecto'


def _normalize_location_id_for_telephony(location_id: str) -> str:
    """
    Convierte IDs Hydra de ubicación (base64) al UUID esperado por APIs telephony/config.
    Si ya viene en UUID, se devuelve tal cual.
    """
    if not location_id:
        return location_id
    if not location_id.startswith('Y2'):
        return location_id
    try:
        decoded = base64.b64decode(f'{location_id}==').decode()
    except Exception:  # noqa: BLE001
        return location_id
    if '/LOCATION/' not in decoded:
        return location_id
    return webex_id_to_uuid(location_id) or location_id


def configurar_permisos_salientes_defecto_ubicacion(
    *,
    token: str,
    location_id: str,
    org_id: str | None = None,
) -> dict[str, Any]:
    """
    Restablece permisos salientes de ubicación para usar configuración por defecto.
    """
    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    normalized_location_id = _normalize_location_id_for_telephony(location_id)

    profile_payload = load_report_json('location_profile.json')
    if profile_payload is not None:
        settings = OutgoingPermissions.model_validate(profile_payload)
    else:
        settings = OutgoingPermissions(use_custom_enabled=True, use_custom_permissions=True)
    if settings.use_custom_enabled is None:
        settings.use_custom_enabled = True
    if settings.use_custom_permissions is None:
        settings.use_custom_permissions = True

    # 2) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'entity_id': normalized_location_id,
        'input_location_id': location_id,
        'settings': model_to_dict(settings),
        'org_id': org_id,
    }

    log('configure_request', request)

    # 3) Ejecución del cambio contra Webex Calling.
    api.telephony.location.permissions_out.configure(
        entity_id=normalized_location_id,
        settings=settings,
        org_id=org_id,
    )

    # 4) Resultado normalizado para logs/pipelines aguas abajo.
    result = {'status': 'success', 'api_response': {'request': request}}
    log('configure_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Configurar permisos salientes por defecto en una ubicación')
    parser.add_argument('--token', default=None)
    parser.add_argument('--csv', default=None, help='CSV con parámetros de entrada (se usa primera fila)')
    parser.add_argument('--location-id', default=None)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()
    args = apply_csv_arguments(args, required=['location_id'], list_fields=[])

    payload = configurar_permisos_salientes_defecto_ubicacion(
        token=get_token(args.token),
        location_id=args.location_id,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
