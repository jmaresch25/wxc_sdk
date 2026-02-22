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
from typing import Any, Callable, get_args, get_origin, get_type_hints

from ._prechecks import run_feature_precheck
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
    CSV_HEADERS as PEOPLE_TO_LOCATION_CSV_HEADERS,
    assign_users_to_locations,
    generate_csv_from_people_json,
)
from .usuarios_configurar_desvio_prefijo53 import configurar_desvio_prefijo53_usuario
from .usuarios_configurar_perfil_saliente_custom import configurar_perfil_saliente_custom_usuario
from .usuarios_modificar_licencias import modificar_licencias_usuario
from .usuarios_remover_licencias import remover_licencias_usuario
from .workspaces_alta import alta_workspace
from .workspaces_anadir_intercom_legacy import anadir_intercom_legacy_workspace
from .workspaces_configurar_desvio_prefijo53 import configurar_desvio_prefijo53_workspace
from .workspaces_configurar_desvio_prefijo53_telephony import configurar_desvio_prefijo53_workspace_telephony
from .workspaces_configurar_perfil_saliente_custom import configurar_perfil_saliente_custom_workspace
from .workspaces_validar_estado_permisos import validar_estado_permisos_workspace

ActionFn = Callable[..., dict[str, Any]]
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = PACKAGE_ROOT / '.artifacts' / 'report' / 'results_manual.csv'


HANDLERS: dict[str, ActionFn] = {

    'ubicacion_alta_numeraciones_desactivadas': alta_numeraciones_desactivadas,
    'ubicacion_actualizar_cabecera': actualizar_cabecera_ubicacion,
    'ubicacion_configurar_llamadas_internas': configurar_llamadas_internas_ubicacion,
    'ubicacion_configurar_permisos_salientes_defecto': configurar_permisos_salientes_defecto_ubicacion,
    'ubicacion_configurar_pstn': configurar_pstn_ubicacion,
    #'usuarios_alta_people': alta_usuario_people,
    #'usuarios_alta_scim': alta_usuario_scim,
    'usuarios_anadir_intercom_legacy': anadir_intercom_legacy_usuario,
    'usuarios_asignar_location_desde_csv': assign_users_to_locations,
    'usuarios_configurar_desvio_prefijo53': configurar_desvio_prefijo53_usuario,
    'usuarios_configurar_perfil_saliente_custom': configurar_perfil_saliente_custom_usuario,
    'usuarios_modificar_licencias': modificar_licencias_usuario,
    'usuarios_remover_licencias': remover_licencias_usuario,
    #'workspaces_alta': alta_workspace,
    #'workspaces_anadir_intercom_legacy': anadir_intercom_legacy_workspace,
    #'workspaces_configurar_desvio_prefijo53': configurar_desvio_prefijo53_workspace,
    #'workspaces_configurar_desvio_prefijo53_telephony': configurar_desvio_prefijo53_workspace_telephony,
    'workspaces_configurar_perfil_saliente_custom': configurar_perfil_saliente_custom_workspace,
    #'workspaces_validar_estado_permisos': validar_estado_permisos_workspace,
}

LOCAL_SCRIPT_DEPENDENCIES: dict[str, list[str]] = {
    # Se alimenta por defecto de su propio CSV de control.
    'usuarios_asignar_location_desde_csv': [],
    #'workspaces_validar_estado_permisos': ['workspace_id'],
}


LOGGER = logging.getLogger(__name__)
MAX_RETRIES_ON_RETRY_AFTER = 3


FEATURE_PRECHECKS: dict[str, dict[str, str]] = {
    'usuarios_configurar_perfil_saliente_custom': {'entity_param': 'person_id', 'entity_type': 'person', 'feature_name': 'outgoing_permissions'},
    'workspaces_configurar_perfil_saliente_custom': {'entity_param': 'workspace_id', 'entity_type': 'workspace', 'feature_name': 'outgoing_permissions'},
    'usuarios_configurar_desvio_prefijo53': {'entity_param': 'person_id', 'entity_type': 'person', 'feature_name': 'call_forwarding'},
    'workspaces_configurar_desvio_prefijo53': {'entity_param': 'workspace_id', 'entity_type': 'workspace', 'feature_name': 'call_forwarding'},
}


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


def _accepts_list(annotation: Any) -> bool:
    """Devuelve True si la anotación acepta una lista (p.ej. list[str] o list[str] | None)."""
    if annotation is inspect._empty:
        return False
    origin = get_origin(annotation)
    if origin is list:
        return True
    if origin in {None, str, int, float, bool, dict, tuple, set}:
        return False
    return any(_accepts_list(arg) for arg in get_args(annotation))


def _coerce_param_value(value: Any, annotation: Any) -> Any:
    """Normaliza tipos para alinear CSV de entrada con la firma del handler."""
    if not _accepts_list(annotation):
        return value
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.split(',') if item.strip()]
    return value




def _preview_csv_head(csv_path: Path, *, max_rows: int = 5) -> dict[str, Any]:
    if not csv_path.exists():
        return {'csv_path': str(csv_path), 'exists': False, 'head': []}
    with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        return {
            'csv_path': str(csv_path),
            'exists': True,
            'columns': reader.fieldnames or [],
            'head': [row for _, row in zip(range(max_rows), reader)],
        }

def _read_parameter_map(csv_path: Path) -> dict[str, Any]:
    """Lee CSV generado por `generar_csv_candidatos_desde_artifacts`: headers=parámetros."""
    with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        return {}

    # CSV multipropósito: tomamos el primer valor no vacío por columna.
    # Esto evita perder parámetros cuando la primera fila no está poblada.
    parameter_map: dict[str, Any] = {}
    for row in rows:
        for key, value in row.items():
            if key == 'script_name' or key in parameter_map:
                continue
            if (value or '').strip() == '':
                continue
            parameter_map[key] = _parse_param_value(value)

    return parameter_map


def _read_parameter_map_from_sources(*, csv_paths: list[Path] | None = None, input_data_dir: Path | None = None) -> dict[str, Any]:
    """Combina parámetros desde múltiples CSV, tomando el primer valor no vacío por columna.

    Prioridad de fuentes:
    1) `csv_paths` en el orden recibido.
    2) CSVs descubiertos en `input_data_dir` en orden alfabético.
    """
    combined: dict[str, Any] = {}
    source_paths: list[Path] = []
    if csv_paths:
        source_paths.extend(csv_paths)
    if input_data_dir is not None:
        source_paths.extend(sorted(input_data_dir.glob('*.csv')))

    if not source_paths:
        return combined

    for path in source_paths:
        if not path.exists():
            continue
        source_map = _read_parameter_map(path)
        for key, value in source_map.items():
            if key in combined or _is_missing_value(value):
                continue
            combined[key] = value
    return combined


def _confirm(script_name: str, auto_confirm: bool) -> bool:
    if auto_confirm:
        return True
    answer = input(f'*+_-/*+_-/*+_-/*+_-/*+_-/*+_-/*+_-/¿Ejecutar {script_name}? [y/N]: ').strip().lower()
    return answer in {'y', 'yes', 's', 'si'}


def _params_for_script(script_name: str, parameter_map: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    required = LOCAL_SCRIPT_DEPENDENCIES.get(script_name, SCRIPT_DEPENDENCIES.get(script_name, []))

    # Caso especial MVP: workspaces_alta también puede ejecutarse en lote con
    # `workspaces_lote_json` sin requerir `display_name`/`location_id`.
    if script_name == 'workspaces_alta' and not _is_missing_value(parameter_map.get('workspaces_lote_json')):
        required = ['workspaces_lote_json']

    # Compatibilidad puntual: algunos CSV usan `remove_license_id` (singular).
    if script_name == 'usuarios_remover_licencias' and _is_missing_value(parameter_map.get('remove_license_ids')):
        singular_value = parameter_map.get('remove_license_id')
        if not _is_missing_value(singular_value):
            parameter_map = {**parameter_map, 'remove_license_ids': singular_value}

    handler = HANDLERS[script_name]
    signature = inspect.signature(handler)

    # No exigir dependencias con valor por defecto en la firma del handler.
    # Esto evita falsos "missing_dependencies" cuando el CSV no incluye
    # parámetros opcionales (p.ej. pstn_connection_type/premise_route_type).
    effective_required = [
        dep
        for dep in required
        if dep not in signature.parameters
        or signature.parameters[dep].default is inspect._empty
    ]

    missing = [dep for dep in effective_required if _is_missing_value(parameter_map.get(dep))]
    if missing:
        return {}, missing

    accepted_params = set(inspect.signature(handler).parameters.keys()) - {'token'}
    try:
        type_hints = get_type_hints(handler)
    except Exception:  # noqa: BLE001
        type_hints = {}
    params = {
        key: _coerce_param_value(value, type_hints.get(key, signature.parameters[key].annotation))
        for key, value in parameter_map.items()
        if key in accepted_params and not _is_missing_value(value)
    }
    return params, []


def _run_script(
    *,
    script_name: str,
    parameter_map: dict[str, Any],
    token: str,
    auto_confirm: bool,
    dry_run: bool,
    precheck_workspace_permissions: bool = False,
) -> dict[str, Any]:
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

    precheck_cfg = FEATURE_PRECHECKS.get(script_name)
    if precheck_cfg and not dry_run:
        entity_id = params.get(precheck_cfg['entity_param'])
        if _is_missing_value(entity_id):
            return {
                'script_name': script_name,
                'status': 'skipped',
                'reason': 'missing_dependencies',
                'missing_dependencies': precheck_cfg['entity_param'],
            }
        precheck_result = run_feature_precheck(
            token=token,
            org_id=params.get('org_id'),
            entity_id=str(entity_id),
            entity_type=precheck_cfg['entity_type'],
            feature_name=precheck_cfg['feature_name'],
        )
        if not precheck_result.get('ok'):
            reason = precheck_result.get('reason', 'unauthorized_feature')
            return {
                'script_name': script_name,
                'status': 'skipped',
                'reason': reason,
                'precheck': precheck_result,
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

    if script_name == 'usuarios_asignar_location_desde_csv':
        report_csv = Path(parameter_map.get('csv_path') or DEFAULT_REPORT_CSV)
        people_json = Path(parameter_map.get('people_json') or DEFAULT_USERS_EXPORT)
        overwrite_csv = bool(parameter_map.get('overwrite_csv'))
        generate_only = bool(parameter_map.get('generate_only'))

        generated_csv = generate_csv_from_people_json(
            people_json=people_json,
            output_csv=report_csv,
            overwrite=overwrite_csv,
        )
        csv_preview = _preview_csv_head(generated_csv)
        invocation_payload['csv_preview'] = csv_preview
        invocation_payload['required_csv_columns'] = PEOPLE_TO_LOCATION_CSV_HEADERS
        LOGGER.info('Invocación preparada (usuarios_asignar_location_desde_csv):\n%s', json.dumps(invocation_payload, indent=2, ensure_ascii=False, sort_keys=True))

        if dry_run:
            return {
                'script_name': script_name,
                'status': 'dry_run',
                'params': params,
                'invocation': invocation_payload,
                'result': {'csv_path': str(generated_csv), 'csv_preview': csv_preview, 'required_csv_columns': PEOPLE_TO_LOCATION_CSV_HEADERS},
            }

        if generate_only:
            return {
                'script_name': script_name,
                'status': 'executed',
                'result': {'csv_path': str(generated_csv), 'generate_only': True, 'csv_preview': csv_preview},
                'invocation': invocation_payload,
            }

        result = assign_users_to_locations(csv_path=generated_csv, token=token, dry_run=False)
        return {
            'script_name': script_name,
            'status': 'executed',
            'result': {'csv_path': str(generated_csv), 'updates': result, 'csv_preview': csv_preview},
            'invocation': invocation_payload,
        }

    if dry_run:
        return {'script_name': script_name, 'status': 'dry_run', 'params': params, 'invocation': invocation_payload}

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
    parser.add_argument('--csv-path', type=Path, action='append', default=None, help='CSV de parámetros (repetible)')
    parser.add_argument('--input-data-dir', type=Path, default=None, help='Directorio con múltiples CSV (*.csv) para combinar parámetros')
    parser.add_argument('--token', default=None)
    parser.add_argument('--script-name', action='append', default=None, help='Filtra por script_name (repetible)')
    parser.add_argument('--auto-confirm', action='store_true', help='Evita input() y confirma todo automáticamente')
    parser.add_argument('--dry-run', action='store_true', help='No llama API, solo valida y muestra payload a ejecutar')
    parser.add_argument('--precheck-workspace-permissions', action='store_true', help='Consulta y muestra permisos de workspace antes de ejecutar scripts workspaces_*')
    args = parser.parse_args()

    _setup_debug_logging()

    csv_paths = args.csv_path or [DEFAULT_CSV]
    parameter_map = _read_parameter_map_from_sources(csv_paths=csv_paths, input_data_dir=args.input_data_dir)
    scripts = args.script_name or sorted(HANDLERS.keys())

    token = '' if args.dry_run else get_token(args.token)
    report: list[dict[str, Any]] = []
    for script_name in scripts:
        report.append(_run_script(script_name=script_name, parameter_map=parameter_map, token=token, auto_confirm=args.auto_confirm, dry_run=args.dry_run, precheck_workspace_permissions=args.precheck_workspace_permissions))

    print(json.dumps({
        'csv_paths': [str(path) for path in csv_paths],
        'input_data_dir': str(args.input_data_dir) if args.input_data_dir else None,
        'results': report,
    }, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
