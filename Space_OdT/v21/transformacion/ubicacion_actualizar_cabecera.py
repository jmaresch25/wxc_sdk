from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
import sys
from typing import Any

from wxc_sdk.telephony.location import CallingLineId, TelephonyLocation

from .common import (
    action_logger,
    apply_standalone_input_arguments,
    create_api,
    get_token,
    load_runtime_env,
    model_to_dict,
)

SCRIPT_NAME = 'ubicacion_actualizar_cabecera'


def actualizar_cabecera_ubicacion(
    *,
    token: str,
    location_id: str,
    phone_number: str,
    org_id: str | None = None,
    calling_line_name: str | None = None,
) -> dict[str, Any]:
    # 1) Inicialización: logger por acción y cliente API autenticado.
    if not location_id:
        raise ValueError('location_id es obligatorio')
    if not phone_number:
        raise ValueError('phone_number es obligatorio')

    log = action_logger(SCRIPT_NAME)
    api = create_api(token)
    # 2) Actualizamos usando el método específico de ubicación con el objeto mínimo requerido.
    calling_line = CallingLineId(phone_number=phone_number)
    if calling_line_name:
        calling_line.name = calling_line_name
    settings = TelephonyLocation(calling_line_id=calling_line)

    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'location_id': location_id,
        'phone_number': phone_number,
        'calling_line_name': calling_line_name,
        'org_id': org_id,
    }
    log('update_request', request)

    batch_job_id = api.telephony.location.update(location_id=location_id, settings=settings, org_id=org_id)
    # 4) Resultado normalizado para logs/pipelines aguas abajo.
    result = {
        'status': 'success',
        'api_response': {'request': request, 'batch_job_id': batch_job_id},
    }
    log('update_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Añadir/actualizar cabecera de ubicación (calling_line_id.phone_number)')
    parser.add_argument('--token', default=None)
    parser.add_argument('--csv', default=None, help='CSV explícito (override); si no se informa se usa --input-dir')
    parser.add_argument('--input-dir', default=None, help='Directorio con Global.csv y Ubicaciones.csv (default: Space_OdT/input_data)')
    parser.add_argument('--location-id', default=None)
    parser.add_argument('--phone-number', default=None)
    parser.add_argument('--calling-line-name', default=None)
    parser.add_argument('--org-id', default=None)
    try:
        args = parser.parse_args()
        args = apply_standalone_input_arguments(
            args,
            required=['location_id', 'phone_number'],
            list_fields=[],
            domain_csv_name='Ubicaciones.csv',
            script_name=SCRIPT_NAME,
            validate_required=False,
        )

        payload = actualizar_cabecera_ubicacion(
            token=get_token(args.token),
            location_id=args.location_id,
            phone_number=args.phone_number,
            org_id=args.org_id,
            calling_line_name=args.calling_line_name,
        )
        print(payload)
    except ValueError as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
