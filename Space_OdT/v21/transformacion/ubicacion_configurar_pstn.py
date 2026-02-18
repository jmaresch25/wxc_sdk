from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
import time
from typing import Any

from wxc_sdk.rest import RestError

from .common import action_logger, apply_csv_arguments, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'ubicacion_configurar_pstn'


def _is_404(error: RestError) -> bool:
    return getattr(error.response, 'status_code', None) == 404


def _read_current_pstn(*, api: Any, location_id: str, org_id: str | None) -> dict[str, Any] | None:
    try:
        return model_to_dict(api.telephony.pstn.read(location_id=location_id, org_id=org_id))
    except RestError as err:
        if _is_404(err):
            return None
        raise


def _ensure_location_enabled_for_calling(*, api: Any, location_id: str, org_id: str | None) -> None:
    try:
        api.telephony.location.details(location_id=location_id, org_id=org_id)
    except RestError as err:
        if _is_404(err):
            raise ValueError(
                'La ubicación no está habilitada para Webex Calling o no pertenece al org indicado. '
                'Primero activa la ubicación con telephony.location.enable_for_calling().'
            ) from err
        raise


def _option_matches_route(*, option: dict[str, Any], route_type: str, route_id: str) -> bool:
    return option.get('routeType') == route_type and option.get('routeId') == route_id


def configurar_pstn_ubicacion(
    *,
    token: str,
    location_id: str,
    premise_route_type: str,
    premise_route_id: str,
    org_id: str | None = None,
) -> dict[str, Any]:
    if premise_route_type not in {'TRUNK', 'ROUTE_GROUP'}:
        raise ValueError('premise_route_type debe ser TRUNK o ROUTE_GROUP')

    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    # 1) Precondición funcional: la ubicación debe existir en telephony/config/locations.
    _ensure_location_enabled_for_calling(api=api, location_id=location_id, org_id=org_id)

    # 2) Opciones disponibles: la ruta objetivo debe existir como opción de conexión.
    options = model_to_dict(api.telephony.pstn.list(location_id=location_id, org_id=org_id))
    if not any(_option_matches_route(option=item, route_type=premise_route_type, route_id=premise_route_id)
               for item in options):
        raise ValueError(
            'La ruta objetivo no aparece en connectionOptions para esta ubicación. '
            'Revisa org_id, location_id, routeType/routeId y que el route group o trunk pertenezca al mismo org.'
        )

    # 3) Estado actual y posible no-op si ya está configurado.
    before = _read_current_pstn(api=api, location_id=location_id, org_id=org_id)
    request = {
        'location_id': location_id,
        'premise_route_type': premise_route_type,
        'premise_route_id': premise_route_id,
        'org_id': org_id,
    }
    log('before_read', {'before': before, 'options': options})
    if before and _option_matches_route(option=before, route_type=premise_route_type, route_id=premise_route_id):
        result = {
            'status': 'success',
            'api_response': {'before': before, 'after': before, 'options': options, 'request': request},
            'message': 'La ubicación ya tenía la PSTN solicitada; no se aplicaron cambios.',
        }
        log('configure_noop', result)
        return result

    # 4) Aplicación del cambio.
    log('configure_request', request)
    api.telephony.pstn.configure(
        location_id=location_id,
        premise_route_type=premise_route_type,
        premise_route_id=premise_route_id,
        org_id=org_id,
    )

    # 5) Verificación post-cambio con pequeño retry por consistencia eventual.
    after = None
    for _ in range(3):
        after = _read_current_pstn(api=api, location_id=location_id, org_id=org_id)
        if after is not None:
            break
        time.sleep(1)

    result = {'status': 'success', 'api_response': {'before': before, 'after': after, 'options': options, 'request': request}}
    if after is None:
        result['warnings'] = [{
            'type': 'pstn_read_after_config_empty',
            'message': 'No se pudo leer el estado PSTN tras configurar; podría ser consistencia eventual o falta de permisos.',
        }]
    log('configure_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Configurar PSTN de una ubicación (SDK-first)')
    parser.add_argument('--token', default=None)
    parser.add_argument('--csv', default=None, help='CSV con parámetros de entrada (se usa primera fila)')
    parser.add_argument('--location-id', default=None)
    parser.add_argument('--premise-route-type', default='ROUTE_GROUP')
    parser.add_argument('--premise-route-id', default=None)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()
    args = apply_csv_arguments(args, required=['location_id', 'premise_route_id'], list_fields=[])

    payload = configurar_pstn_ubicacion(
        token=get_token(args.token),
        location_id=args.location_id,
        premise_route_type=args.premise_route_type,
        premise_route_id=args.premise_route_id,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
