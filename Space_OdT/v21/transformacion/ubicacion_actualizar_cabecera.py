from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
import re
from typing import Any

from wxc_sdk.telephony.location import CallingLineId, TelephonyLocation

from .common import action_logger, apply_csv_arguments, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'ubicacion_actualizar_cabecera'
E164_PATTERN = re.compile(r'^\+[1-9]\d{1,14}$')


def actualizar_cabecera_ubicacion(
    *,
    token: str,
    location_id: str,
    phone_number: str,
    org_id: str | None = None,
    calling_line_name: str | None = None,
) -> dict[str, Any]:
    if not location_id or not location_id.strip():
        raise ValueError('location_id es obligatorio')
    if not phone_number or not phone_number.strip():
        raise ValueError('phone_number es obligatorio')
    if not E164_PATTERN.match(phone_number.strip()):
        raise ValueError('phone_number debe estar en formato E.164 (ejemplo: +34911222333)')

    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)
    # 2) Usamos update() de Location API con payload mínimo (solo calling_line_id).
    settings = TelephonyLocation(
        calling_line_id=CallingLineId(
            phone_number=phone_number.strip(),
            name=calling_line_name,
        )
    )

    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'location_id': location_id,
        'phone_number': phone_number,
        'calling_line_name': calling_line_name,
        'org_id': org_id,
    }
    log('update_request', request)

    batch_job_id = api.telephony.location.update(location_id=location_id.strip(), settings=settings, org_id=org_id)
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
    parser.add_argument('--csv', default=None, help='CSV con parámetros de entrada (se usa primera fila)')
    parser.add_argument('--location-id', default=None)
    parser.add_argument('--phone-number', default=None)
    parser.add_argument('--calling-line-name', default=None)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()
    args = apply_csv_arguments(args, required=['location_id', 'phone_number'], list_fields=[])

    payload = actualizar_cabecera_ubicacion(
        token=get_token(args.token),
        location_id=args.location_id,
        phone_number=args.phone_number,
        org_id=args.org_id,
        calling_line_name=args.calling_line_name,
    )
    print(payload)


if __name__ == '__main__':
    main()
