from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
from typing import Any

from wxc_sdk.rest import RestError

from .common import action_logger, apply_csv_arguments, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'ubicacion_configurar_pstn'


def _find_local_gateway_connection_id(options: list[dict[str, Any]]) -> str:
    """Obtiene el `id` de la opción LOCAL_GATEWAY requerida por el endpoint de configuración."""
    for option in options:
        if option.get('pstn_connection_type') == 'LOCAL_GATEWAY' and option.get('id'):
            return str(option['id'])
    raise ValueError('No se encontró una opción PSTN LOCAL_GATEWAY con id para la ubicación indicada.')


def _enable_location_for_calling(*, api, location_id: str, org_id: str | None, log) -> dict[str, Any]:
    """Garantiza que la location esté habilitada para Webex Calling antes de configurar PSTN."""
    try:
        calling_location = model_to_dict(api.telephony.locations.details(location_id=location_id, org_id=org_id))
        payload = {
            'status': 'already_enabled',
            'location_id': location_id,
            'calling_location': calling_location,
        }
        log('enable_calling_response', payload)
        return payload
    except RestError as error:
        status_code = getattr(getattr(error, 'response', None), 'status_code', None)
        if status_code not in {400, 404}:
            raise

    location = api.locations.details(location_id=location_id, org_id=org_id)
    enabled_location_id = api.telephony.locations.enable_for_calling(location=location, org_id=org_id)
    payload = {
        'status': 'enabled',
        'location_id': enabled_location_id,
    }
    log('enable_calling_response', payload)
    return payload


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

    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    enable_request = {'location_id': location_id, 'org_id': org_id}
    log('enable_calling_request', enable_request)
    enable_result = _enable_location_for_calling(api=api, location_id=location_id, org_id=org_id, log=log)

    if enable_result.get('status') not in {'enabled', 'already_enabled'}:
        raise RuntimeError('No se pudo habilitar la location para Webex Calling; se cancela configuración PSTN.')

    options = model_to_dict(api.telephony.pstn.list(location_id=location_id, org_id=org_id))
    connection_id = _find_local_gateway_connection_id(options)

    # 2) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'location_id': location_id,
        'id': connection_id,
        'premise_route_type': premise_route_type,
        'premise_route_id': premise_route_id,
        'org_id': org_id,
    }
    log('configure_request', {**request, 'options': options})

    # 3) Ejecución del cambio contra Webex Calling.
    api.telephony.pstn.configure(
        location_id=location_id,
        id=connection_id,
        premise_route_type=premise_route_type,
        premise_route_id=premise_route_id,
        org_id=org_id,
    )
    # 4) Resultado normalizado para logs/pipelines aguas abajo.
    result = {
        'status': 'success',
        'api_response': {
            'calling_enablement': enable_result,
            'options': options,
            'request': request,
        },
    }
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
