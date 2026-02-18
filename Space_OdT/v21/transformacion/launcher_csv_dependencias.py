from __future__ import annotations

"""Launcher v21 que consume un CSV con columnas=parámetros."""

import argparse
import csv
import datetime as dt
import inspect
import json
import logging
import time
import traceback
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable

from .common import get_token, load_runtime_env
from .generar_csv_candidatos_desde_artifacts import SCRIPT_DEPENDENCIES
from .ubicacion_actualizar_cabecera import actualizar_cabecera_ubicacion
from .ubicacion_alta_numeraciones_desactivadas import alta_numeraciones_desactivadas
from .ubicacion_configurar_llamadas_internas import configurar_llamadas_internas_ubicacion
from .ubicacion_configurar_permisos_salientes_defecto import configurar_permisos_salientes_defecto_ubicacion
from .ubicacion_configurar_pstn import configurar_pstn_ubicacion
from .usuarios_alta_people import alta_usuario_people
from .usuarios_alta_scim import alta_usuario_scim
from .usuarios_anadir_intercom_legacy import anadir_intercom_legacy_usuario
from .usuarios_asignar_location_desde_csv import (
    DEFAULT_REPORT_CSV,
    DEFAULT_USERS_EXPORT,
    assign_users_to_locations,
    generate_csv_from_people_json,
)
from .usuarios_configurar_desvio_prefijo53 import configurar_desvio_prefijo53_usuario
from .usuarios_configurar_perfil_saliente_custom import configurar_perfil_saliente_custom_usuario
from .usuarios_modificar_licencias import modificar_licencias_usuario
from .workspaces_alta import alta_workspace
from .workspaces_anadir_intercom_legacy import anadir_intercom_legacy_workspace
from .workspaces_configurar_desvio_prefijo53 import configurar_desvio_prefijo53_workspace
from .workspaces_configurar_desvio_prefijo53_telephony import configurar_desvio_prefijo53_workspace_telephony
from .workspaces_configurar_perfil_saliente_custom import configurar_perfil_saliente_custom_workspace
from .workspaces_validar_estado_permisos import validar_estado_permisos_workspace

ActionFn = Callable[..., dict[str, Any]]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CSV = REPO_ROOT / '.artifacts' / 'exports' / 'v21_transformacion_candidatos.csv'

HANDLERS: dict[str, ActionFn] = {
    'ubicacion_actualizar_cabecera': actualizar_cabecera_ubicacion,
    'ubicacion_alta_numeraciones_desactivadas': alta_numeraciones_desactivadas,
    'ubicacion_configurar_llamadas_internas': configurar_llamadas_internas_ubicacion,
    'ubicacion_configurar_permisos_salientes_defecto': configurar_permisos_salientes_defecto_ubicacion,
    'ubicacion_configurar_pstn': configurar_pstn_ubicacion,
    'usuarios_alta_people': alta_usuario_people,
    'usuarios_alta_scim': alta_usuario_scim,
    'usuarios_anadir_intercom_legacy': anadir_intercom_legacy_usuario,
    'usuarios_asignar_location_desde_csv': assign_users_to_locations,
    'usuarios_configurar_desvio_prefijo53': configurar_desvio_prefijo53_usuario,
    'usuarios_configurar_perfil_saliente_custom': configurar_perfil_saliente_custom_usuario,
    'usuarios_modificar_licencias': modificar_licencias_usuario,
    'workspaces_alta': alta_workspace,
    'workspaces_anadir_intercom_legacy': anadir_intercom_legacy_workspace,
    'workspaces_configurar_desvio_prefijo53': configurar_desvio_prefijo53_workspace,
    'workspaces_configurar_desvio_prefijo53_telephony': configurar_desvio_prefijo53_workspace_telephony,
    'workspaces_configurar_perfil_saliente_custom': configurar_perfil_saliente_custom_workspace,
    'workspaces_validar_estado_permisos': validar_estado_permisos_workspace,
}

LOCAL_SCRIPT_DEPENDENCIES: dict[str, list[str]] = {
    # Se alimenta por defecto de su propio CSV de control.
    'usuarios_asignar_location_desde_csv': [],
    'workspaces_validar_estado_permisos': ['workspace_id'],
}

LOGGER = logging.getLogger(__name__)
MAX_RETRIES_ON_RETRY_AFTER = 3


def _retry_after_wait_seconds(retry_after_header: str | None) -> float | None:
    if not retry_after_header:
        return None
    value = retry_after_header.strip()
    if not value:
        return None
    if value.isdigit():
        return max(float(value), 0.0)
    try:
        retry_dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    now = dt.datetime.now(dt.timezone.utc)
    if retry_dt.tzinfo is None:
        retry_dt = retry_dt.replace(tzinfo=dt.timezone.utc)
    return max((retry_dt - now).total_seconds(), 0.0)


def _invoke_with_retry_after(*, handler: ActionFn, token: str, params: dict[str, Any]) -> dict[str, Any]:
    attempt = 0
    while True:
        try:
            return handler(token=token, **params)
        except Exception as exc:  # noqa: BLE001
            attempt += 1
            response = getattr(exc, 'response', None)
            status_code = getattr(response, 'status_code', None)
            headers = getattr(response, 'headers', None) or {}
            retry_after = headers.get('Retry-After') or headers.get('retry-after')
            wait_seconds = _retry_after_wait_seconds(retry_after)
            should_retry = status_code == 429 and wait_seconds is not None and attempt <= MAX_RETRIES_ON_RETRY_AFTER
            if not should_retry:
                raise
            LOGGER.warning('Recibido 429 (Retry-After=%s). Reintento %s/%s en %.2fs', retry_after, attempt, MAX_RETRIES_ON_RETRY_AFTER, wait_seconds)
            time.sleep(wait_seconds)



def _setup_debug_logging() -> None:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    logging.getLogger('wxc_sdk').setLevel(logging.DEBUG)


def _parse_param_value(raw_value: str) -> Any:
    value = (raw_value or '').strip()
    if value == '':
        return None
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    if value.startswith('[') or value.startswith('{'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return raw_value
    return raw_value


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ''
    if isinstance(value, list):
        return len(value) == 0
    return False


def _read_parameter_map(csv_path: Path) -> dict[str, Any]:
    """Lee CSV generado por `generar_csv_candidatos_desde_artifacts`: headers=parámetros, 1 fila de datos."""
    with csv_path.open('r', encoding='utf-8', newline='') as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        return {}

    first_row = rows[0]
    return {
        key: _parse_param_value(value)
        for key, value in first_row.items()
        if key != 'script_name' and (value or '').strip() != ''
    }


def _confirm(script_name: str, auto_confirm: bool) -> bool:
    if auto_confirm:
        return True
    answer = input(f'¿Ejecutar {script_name}? [y/N]: ').strip().lower()
    return answer in {'y', 'yes', 's', 'si'}


def _params_for_script(script_name: str, parameter_map: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    required = LOCAL_SCRIPT_DEPENDENCIES.get(script_name, SCRIPT_DEPENDENCIES.get(script_name, []))

    # Caso especial MVP: workspaces_alta también puede ejecutarse en lote con
    # `workspaces_lote_json` sin requerir `display_name`/`location_id`.
    if script_name == 'workspaces_alta' and not _is_missing_value(parameter_map.get('workspaces_lote_json')):
        required = ['workspaces_lote_json']

    missing = [dep for dep in required if _is_missing_value(parameter_map.get(dep))]
    if missing:
        return {}, missing

    accepted_params = set(inspect.signature(HANDLERS[script_name]).parameters.keys()) - {'token'}
    params = {
        key: value
        for key, value in parameter_map.items()
        if key in accepted_params and not _is_missing_value(value)
    }
    return params, []


def _run_script(*, script_name: str, parameter_map: dict[str, Any], token: str, auto_confirm: bool, dry_run: bool, precheck_workspace_permissions: bool) -> dict[str, Any]:
    if script_name not in HANDLERS:
        return {'script_name': script_name, 'status': 'rejected', 'reason': 'unsupported_script'}

    params, missing = _params_for_script(script_name, parameter_map)
    if missing:
        return {
            'script_name': script_name,
            'status': 'skipped',
            'reason': 'missing_dependencies',
            'missing_dependencies': ';'.join(missing),
        }

    invocation_payload = {
        'script_name': script_name,
        'method': HANDLERS[script_name].__name__,
        'kwargs': {'token': '***' if token else '', **params},
    }
    LOGGER.info('Invocación preparada:\n%s', json.dumps(invocation_payload, indent=2, ensure_ascii=False, sort_keys=True))

    precheck_result: dict[str, Any] | None = None
    if precheck_workspace_permissions and 'workspace_id' in params and script_name.startswith('workspaces_') and not dry_run:
        precheck_result = validar_estado_permisos_workspace(token=token, workspace_id=params['workspace_id'], org_id=params.get('org_id'))
        LOGGER.info('Precheck permisos workspace para %s:\n%s', script_name, json.dumps(precheck_result, indent=2, ensure_ascii=False, sort_keys=True))

    if not _confirm(script_name, auto_confirm=auto_confirm):
        return {'script_name': script_name, 'status': 'skipped', 'reason': 'user_cancelled'}

    if dry_run:
        return {'script_name': script_name, 'status': 'dry_run', 'params': params, 'invocation': invocation_payload}

    if script_name == 'usuarios_asignar_location_desde_csv':
        report_csv = Path(params.get('csv_path') or DEFAULT_REPORT_CSV)
        people_json = Path(params.get('people_json') or DEFAULT_USERS_EXPORT)
        overwrite_csv = bool(params.get('overwrite_csv'))
        generate_only = bool(params.get('generate_only'))

        generated_csv = generate_csv_from_people_json(
            people_json=people_json,
            output_csv=report_csv,
            overwrite=overwrite_csv,
        )
        if generate_only:
            return {
                'script_name': script_name,
                'status': 'executed',
                'result': {'csv_path': str(generated_csv), 'generate_only': True},
                'invocation': invocation_payload,
            }

        result = assign_users_to_locations(csv_path=generated_csv, token=token, dry_run=False)
        return {
            'script_name': script_name,
            'status': 'executed',
            'result': {'csv_path': str(generated_csv), 'updates': result},
            'invocation': invocation_payload,
        }

    try:
        result = _invoke_with_retry_after(handler=HANDLERS[script_name], token=token, params=params)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception('Fallo ejecutando %s con params=%s', script_name, json.dumps(params, ensure_ascii=False, sort_keys=True))
        error_type = getattr(exc, 'error_type', type(exc).__name__)
        error_message = getattr(exc, 'error', str(exc))
        error_params = getattr(exc, 'params', params)
        return {
            'script_name': script_name,
            'status': 'error',
            'error_type': error_type,
            'error': error_message,
            'params': error_params,
            'invocation': invocation_payload,
            'traceback': traceback.format_exc(),
            'precheck': precheck_result,
        }

    return {'script_name': script_name, 'status': 'executed', 'result': result, 'invocation': invocation_payload, 'precheck': precheck_result}


def main() -> None:
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Launcher v21 que usa CSV de parámetros y confirma antes de ejecutar')
    parser.add_argument('--csv-path', type=Path, default=DEFAULT_CSV)
    parser.add_argument('--token', default=None)
    parser.add_argument('--script-name', action='append', default=None, help='Filtra por script_name (repetible)')
    parser.add_argument('--auto-confirm', action='store_true', help='Evita input() y confirma todo automáticamente')
    parser.add_argument('--dry-run', action='store_true', help='No llama API, solo valida y muestra payload a ejecutar')
    parser.add_argument('--precheck-workspace-permissions', action='store_true', help='Consulta y muestra permisos de workspace antes de ejecutar scripts workspaces_*')
    args = parser.parse_args()

    _setup_debug_logging()

    parameter_map = _read_parameter_map(args.csv_path)
    scripts = args.script_name or sorted(HANDLERS.keys())

    token = '' if args.dry_run else get_token(args.token)
    report: list[dict[str, Any]] = []
    for script_name in scripts:
        report.append(_run_script(script_name=script_name, parameter_map=parameter_map, token=token, auto_confirm=args.auto_confirm, dry_run=args.dry_run, precheck_workspace_permissions=args.precheck_workspace_permissions))

    print(json.dumps({'csv_path': str(args.csv_path), 'results': report}, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
