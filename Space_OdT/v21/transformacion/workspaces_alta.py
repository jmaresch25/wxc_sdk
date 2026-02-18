from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
import json
from typing import Any

from wxc_sdk.workspaces import Workspace
from wxc_sdk.workspace_settings.numbers import UpdateWorkspacePhoneNumber

from .common import action_logger, apply_csv_arguments, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'workspaces_alta'


def alta_workspace(
    *,
    token: str,
    display_name: str | None = None,
    location_id: str | None = None,
    org_id: str | None = None,
    workspaces_lote_json: list[dict[str, Any]] | None = None,
    continue_on_error: bool = True,
    skip_existing: bool = True,
) -> dict[str, Any]:
    """
    Alta de workspace con validación previa básica por nombre/location.

    Si se recibe `workspaces_lote_json`, delega en alta masiva en el mismo handler
    para integración con launcher_csv_dependencias.
    """
    if workspaces_lote_json is not None:
        return alta_workspaces_lote(
            token=token,
            workspaces_lote_json=workspaces_lote_json,
            org_id=org_id,
            continue_on_error=continue_on_error,
            skip_existing=skip_existing,
        )

    if not display_name:
        raise ValueError('display_name es requerido cuando no se usa workspaces_lote_json')
    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    existing = list(api.workspaces.list(display_name=display_name, location_id=location_id, org_id=org_id))
    existing_payload = model_to_dict(existing)
    if existing_payload:
        # 5) Resultado normalizado para logs/pipelines aguas abajo.
        result = {
            'status': 'skipped',
            'reason': 'workspace_already_exists',
            'api_response': {'existing': existing_payload},
        }
        log('create_skipped', {'display_name': display_name, 'location_id': location_id, 'org_id': org_id})
        return result

    workspace = Workspace.create(display_name=display_name)
    if location_id:
        workspace.location_id = location_id

    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {'workspace': model_to_dict(workspace), 'org_id': org_id}
    log('create_request', request)

    created = api.workspaces.create(settings=workspace, org_id=org_id)
    created_payload = model_to_dict(created)

    result = {'status': 'success', 'api_response': {'request': request, 'created': created_payload}}
    log('create_response', result)
    return result


def alta_workspaces_lote(
    *,
    token: str,
    workspaces_lote_json: list[dict[str, Any]],
    org_id: str | None = None,
    continue_on_error: bool = True,
    skip_existing: bool = True,
) -> dict[str, Any]:
    """Alta de una lista de workspaces consumida por el launcher CSV.

    Cada elemento del lote soporta:
    - `display_name` o `displayName` (requerido)
    - `location_id` o `locationId` (opcional)
    - `extension` y/o `primary_number` (opcional; aplica update de números)
    """
    if not isinstance(workspaces_lote_json, list):
        raise ValueError('workspaces_lote_json debe ser una lista JSON de objetos')

    log = action_logger('workspaces_alta_lote')
    api = create_api(token)
    report: list[dict[str, Any]] = []
    failures = 0

    for index, item in enumerate(workspaces_lote_json, start=1):
        if not isinstance(item, dict):
            failures += 1
            report.append({'index': index, 'status': 'error', 'error': 'item_no_es_objeto'})
            if not continue_on_error:
                break
            continue

        display_name = item.get('display_name') or item.get('displayName')
        location_id = item.get('location_id') or item.get('locationId')
        extension = item.get('extension')
        primary_number = item.get('primary_number') or item.get('primaryNumber')
        row_result: dict[str, Any] = {
            'index': index,
            'display_name': display_name,
            'location_id': location_id,
        }

        if not display_name:
            failures += 1
            row_result.update({'status': 'error', 'error': 'display_name_requerido'})
            report.append(row_result)
            if not continue_on_error:
                break
            continue

        try:
            existing = list(api.workspaces.list(display_name=display_name, location_id=location_id, org_id=org_id))
            existing_payload = model_to_dict(existing)
            workspace_id = None
            if existing_payload:
                workspace_id = existing_payload[0].get('id') if isinstance(existing_payload[0], dict) else None
                if skip_existing:
                    row_result.update({'status': 'skipped', 'reason': 'workspace_already_exists', 'workspace_id': workspace_id})
                else:
                    failures += 1
                    row_result.update({'status': 'error', 'reason': 'workspace_already_exists', 'workspace_id': workspace_id})
            else:
                workspace = Workspace.create(display_name=display_name)
                if location_id:
                    workspace.location_id = location_id
                created = api.workspaces.create(settings=workspace, org_id=org_id)
                created_payload = model_to_dict(created)
                workspace_id = created_payload.get('id') if isinstance(created_payload, dict) else None
                row_result.update({'status': 'created', 'workspace_id': workspace_id, 'created': created_payload})

            if workspace_id and (extension or primary_number):
                phone_number = primary_number and UpdateWorkspacePhoneNumber(direct_number=primary_number, primary=True) or UpdateWorkspacePhoneNumber(extension=extension)
                if primary_number and extension:
                    phone_number.extension = extension
                api.workspace_settings.numbers.update(workspace_id=workspace_id, phone_numbers=[phone_number], org_id=org_id)
                row_result['numbers_updated'] = {
                    'extension': extension,
                    'primary_number': primary_number,
                }

            log('batch_row_result', row_result)

        except Exception as exc:  # noqa: BLE001
            failures += 1
            row_result.update({'status': 'error', 'error': str(exc)})
            log('batch_row_error', row_result)
            if not continue_on_error:
                report.append(row_result)
                break

        report.append(row_result)

    return {
        'status': 'success' if failures == 0 else 'partial_error',
        'total': len(workspaces_lote_json),
        'failures': failures,
        'results': report,
    }


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Alta de workspace en Webex Calling')
    parser.add_argument('--token', default=None)
    parser.add_argument('--csv', default=None, help='CSV con parámetros de entrada (se usa primera fila)')
    parser.add_argument('--display-name', default=None)
    parser.add_argument('--location-id', default=None)
    parser.add_argument('--org-id', default=None)
    parser.add_argument('--workspaces-lote-json', default=None, help='Lista JSON de workspaces para alta en lote')
    parser.add_argument('--continue-on-error', action='store_true')
    parser.add_argument('--no-skip-existing', action='store_true')
    args = parser.parse_args()
    args = apply_csv_arguments(args, required=[], list_fields=[])

    if args.workspaces_lote_json:
        lote = args.workspaces_lote_json
        if isinstance(lote, str):
            lote = json.loads(lote)
        payload = alta_workspaces_lote(
            token=get_token(args.token),
            workspaces_lote_json=lote,
            org_id=args.org_id,
            continue_on_error=args.continue_on_error,
            skip_existing=not args.no_skip_existing,
        )
        print(payload)
        return

    args = apply_csv_arguments(args, required=['display_name'], list_fields=[])

    payload = alta_workspace(
        token=get_token(args.token),
        display_name=args.display_name,
        location_id=args.location_id,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
