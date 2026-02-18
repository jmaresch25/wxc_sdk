from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
from typing import Any

from wxc_sdk.person_settings.permissions_out import (
    Action,
    CallTypePermission,
    CallingPermissions,
    OutgoingPermissionCallType,
    OutgoingPermissions,
)

from .common import action_logger, apply_csv_arguments, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'workspaces_configurar_perfil_saliente_custom'


def _normalize_call_types(raw_values: list[str] | None) -> set[OutgoingPermissionCallType]:
    values = raw_values or []
    return {OutgoingPermissionCallType(value.strip().upper()) for value in values if value.strip()}


def configurar_perfil_saliente_custom_workspace(
    *,
    token: str,
    workspace_id: str,
    allow_call_types: list[str] | None = None,
    block_call_types: list[str] | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    """
    Configura permisos salientes custom para workspace.
    Por defecto permite todos los tipos salvo los indicados en --block-call-type.
    """
    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    allow_set = _normalize_call_types(allow_call_types)
    block_set = _normalize_call_types(block_call_types)

    calling_permissions = CallingPermissions.allow_all()
    for call_type in block_set:
        setattr(
            calling_permissions,
            call_type.name.lower(),
            CallTypePermission(action=Action.block, transfer_enabled=False),
        )
    for call_type in allow_set:
        setattr(
            calling_permissions,
            call_type.name.lower(),
            CallTypePermission(action=Action.allow, transfer_enabled=True),
        )

    settings = OutgoingPermissions(
        use_custom_enabled=True,
        use_custom_permissions=True,
        calling_permissions=calling_permissions,
    )
    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {'entity_id': workspace_id, 'org_id': org_id, 'settings': model_to_dict(settings)}

    log('configure_request', request)

    # 3) Ejecución del cambio contra Webex Calling.
    api.workspace_settings.permissions_out.configure(entity_id=workspace_id, settings=settings, org_id=org_id)

    # 4) Resultado normalizado para logs/pipelines aguas abajo.
    result = {'status': 'success', 'api_response': {'request': request}}
    log('configure_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Configurar perfil de llamadas salientes custom para workspace')
    parser.add_argument('--token', default=None)
    parser.add_argument('--csv', default=None, help='CSV con parámetros de entrada (se usa primera fila)')
    parser.add_argument('--workspace-id', default=None)
    parser.add_argument('--allow-call-type', action='append', default=None)
    parser.add_argument('--block-call-type', action='append', default=None)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()
    args = apply_csv_arguments(args, required=['workspace_id'], list_fields=['allow_call_type', 'block_call_type'])

    payload = configurar_perfil_saliente_custom_workspace(
        token=get_token(args.token),
        workspace_id=args.workspace_id,
        allow_call_types=args.allow_call_type,
        block_call_types=args.block_call_type,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
