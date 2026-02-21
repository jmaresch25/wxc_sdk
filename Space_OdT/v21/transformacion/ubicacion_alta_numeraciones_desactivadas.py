from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
import sys
from typing import Any

from wxc_sdk.common import NumberState
from wxc_sdk.telephony.location.numbers import TelephoneNumberType

from .common import (
    action_logger,
    apply_standalone_input_arguments,
    create_api,
    get_token,
    load_runtime_env,
    model_to_dict,
)

SCRIPT_NAME = 'ubicacion_alta_numeraciones_desactivadas'


def alta_numeraciones_desactivadas(
    *,
    token: str,
    location_id: str,
    phone_numbers: list[str],
    number_type: TelephoneNumberType = TelephoneNumberType.did,
    org_id: str | None = None,
) -> dict[str, Any]:
    if not phone_numbers:
        raise ValueError('phone_numbers no puede ser vacío')

    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)
    # 2) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'location_id': location_id,
        'phone_numbers': phone_numbers,
        'number_type': str(number_type),
        'state': NumberState.inactive.value,
        'org_id': org_id,
    }
    log('add_numbers_request', request)

    add_response = api.telephony.location.number.add(
        location_id=location_id,
        phone_numbers=phone_numbers,
        number_type=number_type,
        state=NumberState.inactive,
        org_id=org_id,
    )

    # 3) Resultado normalizado para logs/pipelines aguas abajo.
    result = {
        'status': 'success',
        'api_response': {
            'request': request,
            'add_response': model_to_dict(add_response),
        },
    }
    log('add_numbers_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Alta numeraciones en ubicación (estado desactivado)')
    parser.add_argument('--token', default=None)
    parser.add_argument('--csv', default=None, help='CSV explícito (override); si no se informa se usa --input-dir')
    parser.add_argument('--input-dir', default=None, help='Directorio con Global.csv y Ubicaciones.csv (default: Space_OdT/input_data)')
    parser.add_argument('--location-id', default=None)
    parser.add_argument('--phone-number', action='append', default=None, dest='phone_numbers')
    parser.add_argument('--number-type', default='DID', choices=['DID', 'TOLLFREE', 'MOBILE'])
    parser.add_argument('--org-id', default=None)
    try:
        args = parser.parse_args()
        args = apply_standalone_input_arguments(
            args,
            required=['location_id', 'phone_numbers'],
            list_fields=['phone_numbers'],
            domain_csv_name='Ubicaciones.csv',
            script_name=SCRIPT_NAME,
            validate_required=False,
        )

        payload = alta_numeraciones_desactivadas(
            token=get_token(args.token),
            location_id=args.location_id,
            phone_numbers=args.phone_numbers,
            number_type=TelephoneNumberType(args.number_type),
            org_id=args.org_id,
        )
        print(payload)
    except ValueError as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
