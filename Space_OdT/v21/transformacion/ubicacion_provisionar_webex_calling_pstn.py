from __future__ import annotations

"""Provisiona una ubicación para Webex Calling y configura PSTN en un flujo único."""

import argparse
import time
from typing import Any

from wxc_sdk.locations import Location
from wxc_sdk.rest import RestError

from .common import action_logger, apply_csv_arguments, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'ubicacion_provisionar_webex_calling_pstn'


def _is_404(error: RestError) -> bool:
    return getattr(error.response, 'status_code', None) == 404


def _route_match(option: dict[str, Any], route_type: str, route_id: str) -> bool:
    return option.get('routeType') == route_type and option.get('routeId') == route_id


def _location_id(location: Any) -> str:
    return getattr(location, 'location_id', None) or model_to_dict(location).get('id')


def _pick_route(
    *,
    options: list[dict[str, Any]],
    premise_route_type: str | None,
    premise_route_id: str | None,
) -> tuple[str, str]:
    if premise_route_id and premise_route_type:
        if any(_route_match(option, premise_route_type, premise_route_id) for option in options):
            return premise_route_type, premise_route_id
        raise ValueError('La ruta indicada no está disponible en connectionOptions para la ubicación.')

    if premise_route_type and not premise_route_id:
        for option in options:
            if option.get('routeType') == premise_route_type and option.get('routeId'):
                return premise_route_type, option['routeId']
        raise ValueError(f'No hay rutas disponibles para routeType={premise_route_type} en connectionOptions.')

    for option in options:
        route_type = option.get('routeType')
        route_id = option.get('routeId')
        if route_type in {'TRUNK', 'ROUTE_GROUP'} and route_id:
            return route_type, route_id

    raise ValueError('No existe una ruta TRUNK/ROUTE_GROUP utilizable en connectionOptions.')


def provisionar_ubicacion_webex_calling_pstn(
    *,
    token: str,
    location_name: str,
    time_zone: str,
    preferred_language: str,
    announcement_language: str,
    address1: str,
    city: str,
    state: str,
    postal_code: str,
    country: str,
    premise_route_type: str | None = None,
    premise_route_id: str | None = None,
    org_id: str | None = None,
    address2: str | None = None,
) -> dict[str, Any]:
    if premise_route_type and premise_route_type not in {'TRUNK', 'ROUTE_GROUP'}:
        raise ValueError('premise_route_type debe ser TRUNK o ROUTE_GROUP')

    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    # 1) Crear ubicación base (/v1/locations) si no existe.
    location = api.locations.by_name(location_name, org_id=org_id)
    created_location = False
    if location is None:
        location_id = api.locations.create(
            name=location_name,
            time_zone=time_zone,
            preferred_language=preferred_language,
            announcement_language=announcement_language,
            address1=address1,
            address2=address2,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            org_id=org_id,
        )
        created_location = True
        location = api.locations.details(location_id=location_id, org_id=org_id)

    # 2) Habilitar para Webex Calling si aún no lo está.
    enabled_for_calling = False
    location_id = _location_id(location)
    if not location_id:
        raise ValueError('No se pudo resolver location_id de la ubicación encontrada/creada.')

    try:
        api.telephony.location.details(location_id=location_id, org_id=org_id)
    except RestError as err:
        if not _is_404(err):
            raise
        enabled_id = api.telephony.location.enable_for_calling(
            location=Location.model_validate(model_to_dict(location)),
            org_id=org_id,
        )
        enabled_for_calling = bool(enabled_id)

    # 3) Consultar connectionOptions y seleccionar ruta válida.
    options = model_to_dict(api.telephony.pstn.list(location_id=location_id, org_id=org_id))
    selected_route_type, selected_route_id = _pick_route(
        options=options,
        premise_route_type=premise_route_type,
        premise_route_id=premise_route_id,
    )

    # 4) Configurar PSTN (idempotente si ya coincide).
    before = None
    try:
        before = model_to_dict(api.telephony.pstn.read(location_id=location_id, org_id=org_id))
    except RestError as err:
        if not _is_404(err):
            raise

    if before and _route_match(before, selected_route_type, selected_route_id):
        result = {
            'status': 'success',
            'message': 'La ubicación ya tenía la ruta PSTN solicitada.',
            'location_id': location_id,
            'created_location': created_location,
            'enabled_for_calling': enabled_for_calling,
            'selected_route': {'premise_route_type': selected_route_type, 'premise_route_id': selected_route_id},
            'api_response': {'before': before, 'after': before, 'options': options},
        }
        log('provision_noop', result)
        return result

    api.telephony.pstn.configure(
        location_id=location_id,
        premise_route_type=selected_route_type,
        premise_route_id=selected_route_id,
        org_id=org_id,
    )

    # 5) Verificar con retry corto (consistencia eventual).
    after = None
    for _ in range(3):
        try:
            after = model_to_dict(api.telephony.pstn.read(location_id=location_id, org_id=org_id))
            break
        except RestError as err:
            if not _is_404(err):
                raise
            time.sleep(1)

    result = {
        'status': 'success',
        'location_id': location_id,
        'created_location': created_location,
        'enabled_for_calling': enabled_for_calling,
        'selected_route': {'premise_route_type': selected_route_type, 'premise_route_id': selected_route_id},
        'api_response': {'before': before, 'after': after, 'options': options},
    }
    if after is None:
        result['warnings'] = ['No se pudo confirmar PSTN con read() tras configurar (consistencia eventual o permisos).']
    log('provision_result', result)
    return result


def main() -> None:
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Crear ubicación, habilitar Webex Calling y configurar PSTN')
    parser.add_argument('--token', default=None)
    parser.add_argument('--csv', default=None, help='CSV con parámetros (se usa primera fila)')
    parser.add_argument('--location-name', default=None)
    parser.add_argument('--time-zone', default='Europe/Madrid')
    parser.add_argument('--preferred-language', default='es_ES')
    parser.add_argument('--announcement-language', default='es_ES')
    parser.add_argument('--address1', default=None)
    parser.add_argument('--address2', default=None)
    parser.add_argument('--city', default=None)
    parser.add_argument('--state', default=None)
    parser.add_argument('--postal-code', default=None)
    parser.add_argument('--country', default=None)
    parser.add_argument('--premise-route-type', default=None)
    parser.add_argument('--premise-route-id', default=None)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()
    args = apply_csv_arguments(
        args,
        required=['location_name', 'address1', 'city', 'state', 'postal_code', 'country'],
        list_fields=[],
    )

    payload = provisionar_ubicacion_webex_calling_pstn(
        token=get_token(args.token),
        location_name=args.location_name,
        time_zone=args.time_zone,
        preferred_language=args.preferred_language,
        announcement_language=args.announcement_language,
        address1=args.address1,
        address2=args.address2,
        city=args.city,
        state=args.state,
        postal_code=args.postal_code,
        country=args.country,
        premise_route_type=args.premise_route_type,
        premise_route_id=args.premise_route_id,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
