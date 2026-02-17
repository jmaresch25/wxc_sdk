from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
from typing import Any

from .common import action_logger, apply_csv_arguments, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'workspaces_configurar_desvio_prefijo53_telephony'


def _workspace_forwarding_url(*, api, workspace_id: str) -> str:
    return api.session.ep(f'telephony/config/workspaces/{workspace_id}/callForwarding')


def _workspace_forwarding_params(*, org_id: str | None) -> dict[str, str] | None:
    return org_id and {'orgId': org_id} or None


def _read_forwarding(*, api, workspace_id: str, org_id: str | None) -> dict[str, Any]:
    url = _workspace_forwarding_url(api=api, workspace_id=workspace_id)
    params = _workspace_forwarding_params(org_id=org_id)
    return model_to_dict(api.session.rest_get(url=url, params=params))


def _configure_forwarding(*, api, workspace_id: str, org_id: str | None, destination: str) -> None:
    url = _workspace_forwarding_url(api=api, workspace_id=workspace_id)
    params = _workspace_forwarding_params(org_id=org_id)
    payload = {
        'enabled': True,
        'destination': destination,
        'ringReminderEnabled': False,
        'destinationVoicemailEnabled': False,
    }
    api.session.rest_put(url=url, params=params, json=payload)


def _destination_is_available(*, api, workspace_id: str, org_id: str | None, destination: str) -> bool:
    candidates = list(api.workspace_settings.available_numbers.call_forward(
        entity_id=workspace_id,
        phone_number=[destination],
        org_id=org_id,
    ))
    if not candidates:
        return False
    return any((candidate.phone_number or '').strip() == destination for candidate in candidates)


def configurar_desvio_prefijo53_workspace_telephony(
    *,
    token: str,
    workspace_id: str,
    extension: str,
    destination: str | None = None,
    org_id: str | None = None,
    validate_destination: bool = False,
) -> dict[str, Any]:
    """
    Configura desvío incondicional del workspace con endpoint telephony/config/workspaces.
    """
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    target_destination = destination or f'53{extension}'
    request = {
        'workspace_id': workspace_id,
        'org_id': org_id,
        'destination': target_destination,
        'validate_destination': validate_destination,
        'endpoint': f'telephony/config/workspaces/{workspace_id}/callForwarding',
    }

    if validate_destination:
        request['destination_available'] = _destination_is_available(
            api=api,
            workspace_id=workspace_id,
            org_id=org_id,
            destination=target_destination,
        )
        if not request['destination_available']:
            result = {
                'status': 'rejected',
                'reason': 'destination_not_available_for_call_forwarding',
                'api_response': {'request': request},
            }
            log('configure_rejected', result)
            return result

    before = _read_forwarding(api=api, workspace_id=workspace_id, org_id=org_id)
    log('before_read', {'before': before})
    log('configure_request', request)

    _configure_forwarding(
        api=api,
        workspace_id=workspace_id,
        org_id=org_id,
        destination=target_destination,
    )
    after = _read_forwarding(api=api, workspace_id=workspace_id, org_id=org_id)

    result = {'status': 'success', 'api_response': {'before': before, 'after': after, 'request': request}}
    log('configure_response', result)
    return result


def main() -> None:
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Configurar desvío prefijo 53 para workspace (telephony/config)')
    parser.add_argument('--token', default=None)
    parser.add_argument('--csv', default=None, help='CSV con parámetros de entrada (se usa primera fila)')
    parser.add_argument('--workspace-id', default=None)
    parser.add_argument('--extension', default=None)
    parser.add_argument('--destination', default=None)
    parser.add_argument('--org-id', default=None)
    parser.add_argument('--validate-destination', action='store_true', help='Valida destino con available_numbers.call_forward antes de aplicar')
    args = parser.parse_args()
    args = apply_csv_arguments(args, required=['workspace_id', 'extension'], list_fields=[])

    payload = configurar_desvio_prefijo53_workspace_telephony(
        token=get_token(args.token),
        workspace_id=args.workspace_id,
        extension=args.extension,
        destination=args.destination,
        org_id=args.org_id,
        validate_destination=args.validate_destination,
    )
    print(payload)


if __name__ == '__main__':
    main()
