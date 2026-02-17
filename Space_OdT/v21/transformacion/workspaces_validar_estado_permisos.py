from __future__ import annotations

"""Validador previo para visualizar acceso a permisos de calling en workspaces."""

import argparse
from typing import Any, Callable

from .common import action_logger, apply_csv_arguments, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'workspaces_validar_estado_permisos'


def _as_error_payload(exc: Exception) -> dict[str, Any]:
    response = getattr(exc, 'response', None)
    detail = {
        'error_type': type(exc).__name__,
        'message': str(exc),
    }
    status_code = getattr(response, 'status_code', None)
    if status_code is not None:
        detail['status_code'] = status_code
    code = getattr(exc, 'code', None)
    if code:
        detail['error_code'] = code
    description = (getattr(exc, 'description', '') or '').strip()
    if description:
        detail['description'] = description
    return detail


def _run_check(*, name: str, reader: Callable[[], Any]) -> dict[str, Any]:
    result: dict[str, Any] = {'check': name}
    try:
        data = reader()
    except Exception as exc:  # noqa: BLE001
        payload = _as_error_payload(exc)
        unauthorized = payload.get('status_code') == 400 and payload.get('error_code') == 4003
        result['status'] = 'unauthorized' if unauthorized else 'error'
        result['error'] = payload
        return result

    result['status'] = 'ok'
    result['snapshot'] = model_to_dict(data)
    return result


def validar_estado_permisos_workspace(*, token: str, workspace_id: str, org_id: str | None = None) -> dict[str, Any]:
    """Visualiza si el token/tenant puede leer callForwarding y outgoingPermission del workspace."""
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    checks = [
        _run_check(
            name='workspace_forwarding_read',
            reader=lambda: api.workspace_settings.forwarding.read(entity_id=workspace_id, org_id=org_id),
        ),
        _run_check(
            name='workspace_outgoing_permission_read',
            reader=lambda: api.workspace_settings.permissions_out.read(entity_id=workspace_id, org_id=org_id),
        ),
    ]

    summary = {
        'ok': sum(1 for item in checks if item['status'] == 'ok'),
        'unauthorized': sum(1 for item in checks if item['status'] == 'unauthorized'),
        'error': sum(1 for item in checks if item['status'] == 'error'),
    }

    result = {
        'status': 'success',
        'workspace_id': workspace_id,
        'org_id': org_id,
        'summary': summary,
        'checks': checks,
        'hint': 'Si hay unauthorized(4003), revisar scopes/rol admin de calling y feature enablement del tenant.',
    }
    log('permission_status', result)
    return result


def main() -> None:
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Validador previo de permisos de workspace (forwarding/outgoing)')
    parser.add_argument('--token', default=None)
    parser.add_argument('--csv', default=None, help='CSV con parámetros de entrada (se usa primera fila)')
    parser.add_argument('--workspace-id', default=None)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()
    args = apply_csv_arguments(args, required=['workspace_id'], list_fields=[])

    payload = validar_estado_permisos_workspace(
        token=get_token(args.token),
        workspace_id=args.workspace_id,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
