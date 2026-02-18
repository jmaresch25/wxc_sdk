from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas.

Pre-requisitos operativos:
- Token de administrador (admin de organización o partner admin delegado).
- Scopes con lectura/escritura de usuarios y calling settings (p.ej. `spark-admin:people_read`
  + scopes de telephony/person settings para leer/escribir desvíos).
- Usuario objetivo (`person_id`) con servicio/licencia de Webex Calling activo.
"""

import argparse
from typing import Any

from wxc_sdk.rest import RestError
from wxc_sdk.person_settings.forwarding import (
    CallForwardingAlways,
    CallForwardingPerson,
    PersonForwardingSetting,
)

from .common import action_logger, apply_csv_arguments, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'usuarios_configurar_desvio_prefijo53'


class CallingEligibilityError(RuntimeError):
    """Error operativo normalizado para launcher_csv_dependencias.py."""

    def __init__(self, *, error_type: str, error: str, params: dict[str, Any]):
        super().__init__(error)
        self.error_type = error_type
        self.error = error
        self.params = params


def _is_unauthorized_forwarding_read(error: RestError) -> bool:
    description = (error.description or '').lower()
    return error.code == 4003 and 'usercallforwardingalwaysgetrequest' in description


def _assert_person_calling_eligibility(*, api, person_id: str, org_id: str | None, log) -> dict[str, Any]:
    """Valida que el token y el usuario permiten operar features de Webex Calling."""
    guidance_params = {
        'person_id': person_id,
        'org_id': org_id,
        'required_scopes': [
            'spark-admin:people_read',
            'scopes admin de Webex Calling/person settings para call forwarding',
        ],
        'required_role': 'admin de la organización (o partner admin con delegación)',
        'required_user_state': 'usuario con servicio/licencia Webex Calling (extension/locationId)',
    }
    try:
        person_payload = model_to_dict(api.people.details(person_id=person_id, calling_data=True))
    except RestError as error:
        description = (error.description or '').lower()
        status_code = getattr(getattr(error, 'response', None), 'status_code', None)
        if status_code in {401, 403} or 'scope' in description or 'admin' in description or 'callingdata' in description:
            raise CallingEligibilityError(
                error_type='calling_eligibility_permission_denied',
                error=(
                    'No se pudo validar elegibilidad Calling del usuario: token sin permisos suficientes o sin rol admin. '
                    'Acción: usar token admin con scope spark-admin:people_read y permisos de person settings/calling; '
                    'verificar delegación del admin y que el person_id pertenezca a su organización.'
                ),
                params=guidance_params,
            ) from error
        if status_code == 404:
            raise CallingEligibilityError(
                error_type='calling_eligibility_person_not_found',
                error='No existe el person_id indicado. Acción: validar person_id en Control Hub/export antes de reintentar.',
                params=guidance_params,
            ) from error
        raise

    has_calling_service = bool(person_payload.get('extension') and person_payload.get('locationId') or person_payload.get('location_id'))
    if not has_calling_service:
        raise CallingEligibilityError(
            error_type='calling_eligibility_user_without_calling',
            error=(
                'El usuario no es elegible para Calling (sin extensión/ubicación de Calling). '
                'Acción: asignar licencia/servicio Webex Calling y ubicación al usuario antes de configurar desvío.'
            ),
            params=guidance_params,
        )

    log('calling_eligibility_ok', {'person_id': person_id, 'org_id': org_id, 'calling_summary': {
        'extension': person_payload.get('extension'),
        'location_id': person_payload.get('locationId') or person_payload.get('location_id'),
    }})
    return person_payload


def _read_forwarding_with_fallback(*, api, person_id: str, org_id: str | None, log) -> dict[str, Any]:
    """
    Lee call forwarding priorizando el endpoint moderno y con fallback al endpoint telephony/config.
    """
    params = org_id and {'orgId': org_id} or None
    try:
        return model_to_dict(api.person_settings.forwarding.read(entity_id=person_id, org_id=org_id))
    except RestError as error:
        if not _is_unauthorized_forwarding_read(error):
            raise
        log('forwarding_read_fallback', {
            'reason': str(error),
            'primary_endpoint': f'people/{person_id}/features/callForwarding',
            'fallback_endpoint': f'telephony/config/people/{person_id}/callForwarding',
            'params': params,
        })
        url = api.session.ep(f'telephony/config/people/{person_id}/callForwarding')
        return model_to_dict(api.session.rest_get(url=url, params=params))


def _configure_forwarding_with_fallback(*, api, person_id: str, org_id: str | None,
                                        forwarding: PersonForwardingSetting, log) -> None:
    params = org_id and {'orgId': org_id} or None
    try:
        api.person_settings.forwarding.configure(entity_id=person_id, forwarding=forwarding, org_id=org_id)
        return
    except RestError as error:
        if not _is_unauthorized_forwarding_read(error):
            raise
        payload = forwarding.call_forwarding.always.model_dump(mode='json', by_alias=True, exclude_none=True)
        payload = {
            'enabled': payload.get('enabled', True),
            'destination': payload.get('destination', ''),
            'ringReminderEnabled': payload.get('ringReminderEnabled', False),
            'destinationVoicemailEnabled': payload.get('destinationVoicemailEnabled', False),
        }
        log('forwarding_configure_fallback', {
            'reason': str(error),
            'primary_endpoint': f'people/{person_id}/features/callForwarding',
            'fallback_endpoint': f'telephony/config/people/{person_id}/callForwarding',
            'params': params,
            'payload': payload,
        })
        url = api.session.ep(f'telephony/config/people/{person_id}/callForwarding')
        api.session.rest_put(url=url, params=params, json=payload)


def configurar_desvio_prefijo53_usuario(
    *,
    token: str,
    person_id: str,
    extension: str,
    destination: str | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    """
    Configura desvío incondicional del usuario a plataforma legacy con prefijo 53.
    """
    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    # 1.1) Pre-chequeo obligatorio: corta temprano si token/usuario no habilitan Calling.
    _assert_person_calling_eligibility(api=api, person_id=person_id, org_id=org_id, log=log)

    target_destination = destination or f'53{extension}'
    forwarding = PersonForwardingSetting(
        call_forwarding=CallForwardingPerson(
            always=CallForwardingAlways(
                enabled=True,
                destination=target_destination,
                destination_voicemail_enabled=False,
                ring_reminder_enabled=False,
            )
        )
    )
    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'entity_id': person_id,
        'org_id': org_id,
        'forwarding': model_to_dict(forwarding),
    }

    log('configure_request', request)

    # 3) Ejecución del cambio contra Webex Calling.
    _configure_forwarding_with_fallback(api=api, person_id=person_id, org_id=org_id, forwarding=forwarding, log=log)

    # 4) Resultado normalizado para logs/pipelines aguas abajo.
    result = {'status': 'success', 'api_response': {'request': request}}
    log('configure_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Configurar desvío incondicional a prefijo 53 para un usuario')
    parser.add_argument('--token', default=None)
    parser.add_argument('--csv', default=None, help='CSV con parámetros de entrada (se usa primera fila)')
    parser.add_argument('--person-id', default=None)
    parser.add_argument('--extension', default=None, help='Extensión base para construir destino 53+extension')
    parser.add_argument('--destination', default=None, help='Destino explícito, si no se usa 53+extension')
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()
    args = apply_csv_arguments(args, required=['person_id', 'extension'], list_fields=[])

    payload = configurar_desvio_prefijo53_usuario(
        token=get_token(args.token),
        person_id=args.person_id,
        extension=args.extension,
        destination=args.destination,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
