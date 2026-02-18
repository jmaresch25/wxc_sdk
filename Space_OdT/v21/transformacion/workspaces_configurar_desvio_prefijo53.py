from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
from typing import Any

from wxc_sdk.rest import RestError
from wxc_sdk.person_settings.forwarding import (
    CallForwardingAlways,
    CallForwardingPerson,
    PersonForwardingSetting,
)

from .common import action_logger, apply_csv_arguments, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'workspaces_configurar_desvio_prefijo53'


def _is_busy_forwarding_unauthorized(error: Exception) -> bool:
    """Detecta el 4003 específico de Webex para lectura/escritura de rama busy."""
    if not isinstance(error, RestError):
        return False
    return error.code == 4003 and 'UserCallForwardingBusy' in (error.description or '')


def _workspace_call_forwarding_endpoint(workspace_id: str) -> str:
    """Endpoint alternativo de telephony config para workspaces."""
    return f'https://webexapis.com/v1/telephony/config/workspaces/{workspace_id}/callForwarding'


def _fallback_payload(destination: str) -> dict[str, Any]:
    """Payload mínimo (solo Always) para escenarios donde Busy no está autorizado."""
    return {
        'callForwarding': {
            'always': {
                'enabled': True,
                'destination': destination,
                'destinationVoicemailEnabled': True,
                'ringReminderEnabled': True,
            }
        }
    }


def configurar_desvio_prefijo53_workspace(
    *,
    token: str,
    workspace_id: str,
    extension: str,
    destination: str | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    """
    Configura desvío incondicional del workspace a plataforma legacy con prefijo 53.
    """
    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    read_strategy = 'not_used'

    target_destination = destination or f'53{extension}'
    forwarding = PersonForwardingSetting(
        call_forwarding=CallForwardingPerson(
            always=CallForwardingAlways(
                enabled=True,
                destination=target_destination,
                destination_voicemail_enabled=True,
                ring_reminder_enabled=True,
            ),
            busy=CallForwardingPerson.default().busy,
            no_answer=CallForwardingPerson.default().no_answer,
        ),
        business_continuity=PersonForwardingSetting.default().business_continuity,
    )

    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'entity_id': workspace_id,
        'org_id': org_id,
        'read_strategy': read_strategy,
        'configure_strategies': [
            'sdk_workspace_settings.forwarding.configure',
            'rest_put telephony/config/workspaces/{workspaceId}/callForwarding (payload mínimo Always)',
        ],
        'settings': model_to_dict(forwarding),
        'fallback_settings': _fallback_payload(target_destination),
    }
    log('configure_request', request)

    # 4) Ejecución del cambio contra Webex Calling.
    configure_strategy = 'sdk_workspace_settings.forwarding.configure'
    try:
        api.workspace_settings.forwarding.configure(entity_id=workspace_id, forwarding=forwarding, org_id=org_id)
    except Exception as error:
        if not _is_busy_forwarding_unauthorized(error):
            raise
        configure_strategy = 'rest_put telephony/config/workspaces/{workspaceId}/callForwarding (payload mínimo Always)'
        params = org_id and {'orgId': org_id} or None
        api.session.rest_put(
            url=_workspace_call_forwarding_endpoint(workspace_id),
            params=params,
            json=_fallback_payload(target_destination),
        )

    # 4) Resultado normalizado para logs/pipelines aguas abajo.
    result = {
        'status': 'success',
        'api_response': {
            'request': request,
            'configure_strategy_used': configure_strategy,
            'note': (
                'Si aparece 4003 UserCallForwardingBusy*, el script intenta automáticamente método alternativo '
                'vía /telephony/config/workspaces/{workspaceId}/callForwarding con payload mínimo Always.'
            ),
        },
    }
    log('configure_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Configurar desvío prefijo 53 para workspace')
    parser.add_argument('--token', default=None)
    parser.add_argument('--csv', default=None, help='CSV con parámetros de entrada (se usa primera fila)')
    parser.add_argument('--workspace-id', default=None)
    parser.add_argument('--extension', default=None)
    parser.add_argument('--destination', default=None)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()
    args = apply_csv_arguments(args, required=['workspace_id', 'extension'], list_fields=[])

    payload = configurar_desvio_prefijo53_workspace(
        token=get_token(args.token),
        workspace_id=args.workspace_id,
        extension=args.extension,
        destination=args.destination,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
