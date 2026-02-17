from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
import base64
from typing import Any

from wxc_sdk.common import RouteIdentity

from .common import action_logger, apply_csv_arguments, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'ubicacion_configurar_llamadas_internas'


def _decode_hydra_resource_type(webex_id: str) -> str | None:
    """Devuelve el tipo del recurso Hydra embebido en un ID Webex (p.ej. ROUTEGROUP, TRUNK)."""
    try:
        padding = '=' * ((4 - len(webex_id) % 4) % 4)
        decoded = base64.b64decode(f'{webex_id}{padding}').decode()
    except Exception:
        return None

    parts = decoded.split('/')
    if len(parts) < 2:
        return None
    return parts[-2].upper()


def configurar_llamadas_internas_ubicacion(
    *,
    token: str,
    location_id: str,
    enable_unknown_extension_route_policy: bool,
    premise_route_id: str | None = None,
    premise_route_type: str | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    if premise_route_type and premise_route_type not in {'TRUNK', 'ROUTE_GROUP'}:
        raise ValueError('premise_route_type debe ser TRUNK o ROUTE_GROUP')
    if enable_unknown_extension_route_policy and (not premise_route_id or not premise_route_type):
        raise ValueError('Si habilitas la política debes informar premise_route_id y premise_route_type')
    if enable_unknown_extension_route_policy:
        decoded_type = _decode_hydra_resource_type(premise_route_id)
        expected_type = {'ROUTE_GROUP': {'ROUTEGROUP', 'ROUTE_GROUP'}, 'TRUNK': {'TRUNK'}}[premise_route_type]
        if decoded_type and decoded_type not in expected_type:
            raise ValueError(
                f'premise_route_id no coincide con premise_route_type={premise_route_type}: '
                f'tipo decodificado={decoded_type}'
            )

    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    settings = api.telephony.location.internal_dialing.read(location_id=location_id, org_id=org_id)
    # 2) Snapshot previo: leemos estado actual para trazabilidad y rollback manual.
    before = model_to_dict(settings)

    settings.enable_unknown_extension_route_policy = enable_unknown_extension_route_policy
    if enable_unknown_extension_route_policy:
        settings.unknown_extension_route_identity = RouteIdentity(id=premise_route_id, type=premise_route_type)
    else:
        settings.unknown_extension_route_identity = None

    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'location_id': location_id,
        'enable_unknown_extension_route_policy': enable_unknown_extension_route_policy,
        'premise_route_id': premise_route_id,
        'premise_route_type': premise_route_type,
        'org_id': org_id,
    }
    log('before_read', {'before': before})
    log('update_request', request)

    # 4) Ejecución del cambio contra Webex Calling.
    api.telephony.location.internal_dialing.update(location_id=location_id, update=settings, org_id=org_id)
    after = model_to_dict(api.telephony.location.internal_dialing.read(location_id=location_id, org_id=org_id))

    # 5) Resultado normalizado para logs/pipelines aguas abajo.
    result = {'status': 'success', 'api_response': {'before': before, 'after': after, 'request': request}}
    log('update_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Configurar llamadas internas de una ubicación (internal dialing)')
    parser.add_argument('--token', default=None)
    parser.add_argument('--csv', default=None, help='CSV con parámetros de entrada (se usa primera fila)')
    parser.add_argument('--location-id', default=None)
    parser.add_argument('--enable-unknown-extension-route-policy', action='store_true')
    parser.add_argument('--premise-route-id', default=None)
    parser.add_argument('--premise-route-type', default=None, choices=['TRUNK', 'ROUTE_GROUP'])
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()
    args = apply_csv_arguments(args, required=['location_id'], list_fields=[])

    payload = configurar_llamadas_internas_ubicacion(
        token=get_token(args.token),
        location_id=args.location_id,
        enable_unknown_extension_route_policy=args.enable_unknown_extension_route_policy,
        premise_route_id=args.premise_route_id,
        premise_route_type=args.premise_route_type,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
