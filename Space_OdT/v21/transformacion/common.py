from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import datetime as dt
import csv
import json
import os
from argparse import Namespace
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from wxc_sdk import WebexSimpleApi


def load_runtime_env() -> None:
    # Busca .env en cwd y padres para soportar ejecución desde distintos entrypoints.
    cwd = Path.cwd()
    package_root = Path(__file__).resolve().parents[3]
    env_candidates = [cwd / '.env', *[parent / '.env' for parent in cwd.parents], package_root / '.env']
    seen: set[str] = set()
    for env_path in env_candidates:
        resolved = str(env_path.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        if env_path.is_file():
            load_dotenv(dotenv_path=env_path, override=True)


def get_token(explicit_token: str | None = None) -> str:
    token = explicit_token or os.getenv('WEBEX_ACCESS_TOKEN')
    if not token:
        raise ValueError('WEBEX_ACCESS_TOKEN no definido (ni --token).')
    return token


def create_api(token: str) -> WebexSimpleApi:
    return WebexSimpleApi(tokens=token)


def load_report_json(filename: str) -> dict[str, Any] | None:
    report_file = Path(__file__).resolve().parents[2] / '.artifacts' / 'report' / filename
    if not report_file.is_file():
        return None
    with report_file.open('r', encoding='utf-8') as handle:
        return json.load(handle)


def action_logger(script_name: str):
    # Logger JSONL por script para auditoría de requests/responses funcionales.
    log_file = Path(__file__).resolve().parent / 'logs' / f'{script_name}.log'
    log_file.parent.mkdir(parents=True, exist_ok=True)

    def _log(event: str, payload: dict[str, Any]) -> None:
        line = {
            'ts': dt.datetime.now(dt.timezone.utc).isoformat(),
            'action_id': script_name,
            'event': event,
            'payload': payload,
        }
        with log_file.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + '\n')

    return _log


def model_to_dict(value: Any) -> Any:
    # Serialización defensiva compatible con modelos pydantic y listas anidadas.
    if hasattr(value, 'model_dump'):
        try:
            return value.model_dump(mode='json', by_alias=True, exclude_none=True)
        except TypeError:
            return value.model_dump()
    if isinstance(value, list):
        return [model_to_dict(item) for item in value]
    return value


def apply_csv_arguments(
    args: Namespace,
    *,
    required: list[str],
    list_fields: list[str] | None = None,
) -> Namespace:
    """Aplica parámetros desde --csv si existe y valida requeridos tras merge CLI/CSV."""
    csv_file = getattr(args, 'csv', None)
    if not csv_file:
        _assert_required_args(args, required)
        return args

    with Path(csv_file).open('r', encoding='utf-8-sig', newline='') as handle:
        row = next(csv.DictReader(handle), None)
    if row is None:
        raise ValueError(f'CSV vacío: {csv_file}')

    list_fields = list_fields or []
    for field in required + list_fields:
        current_value = getattr(args, field, None)
        if current_value not in (None, [], ''):
            continue
        raw_value = row.get(field)
        if raw_value in (None, ''):
            continue
        if field in list_fields:
            normalized = [item.strip() for item in raw_value.replace('|', ',').split(',') if item.strip()]
            setattr(args, field, normalized)
        else:
            setattr(args, field, raw_value)

    _assert_required_args(args, required)
    return args


def apply_standalone_input_arguments(
    args: Namespace,
    *,
    required: list[str],
    list_fields: list[str] | None = None,
    domain_csv_name: str,
    script_name: str,
) -> Namespace:
    """Resuelve input_dir standalone y aplica merge de Global.csv + CSV de dominio.

    Prioridad para cada campo:
      1) CLI explícito del argumento (por ejemplo --location-id)
      2) primera fila del CSV de dominio (Ubicaciones/Usuarios/Workspaces)
      3) primera fila de Global.csv
    """
    log = action_logger(script_name)
    input_dir = Path(getattr(args, 'input_dir', '') or Path(__file__).resolve().parents[2] / 'input_data')
    setattr(args, 'input_dir', str(input_dir))

    csv_argument = getattr(args, 'csv', None)
    if csv_argument:
        log('input_resolution', {'mode': 'explicit_csv', 'csv': csv_argument})
        return apply_csv_arguments(args, required=required, list_fields=list_fields)

    global_path = _find_csv_case_insensitive(input_dir, 'Global.csv')
    domain_path = _find_csv_case_insensitive(input_dir, domain_csv_name)

    if global_path is None:
        raise ValueError(f'No se encontró Global.csv dentro de input_dir={input_dir}')
    if domain_path is None:
        raise ValueError(f'No se encontró {domain_csv_name} dentro de input_dir={input_dir}')

    global_row = _first_csv_row(global_path)
    domain_row = _first_csv_row(domain_path)
    if global_row is None:
        raise ValueError(f'CSV vacío: {global_path}')
    if domain_row is None:
        raise ValueError(f'CSV vacío: {domain_path}')

    list_fields = list_fields or []
    log(
        'input_resolution',
        {
            'mode': 'input_dir_auto',
            'input_dir': str(input_dir),
            'global_csv': str(global_path),
            'domain_csv': str(domain_path),
            'required': required,
            'list_fields': list_fields,
        },
    )

    for field in required + list_fields:
        current_value = getattr(args, field, None)
        if current_value not in (None, [], ''):
            continue

        raw_value = domain_row.get(field)
        if raw_value in (None, ''):
            raw_value = global_row.get(field)
        if raw_value in (None, ''):
            continue

        if field in list_fields:
            normalized = [item.strip() for item in raw_value.replace('|', ',').split(',') if item.strip()]
            setattr(args, field, normalized)
        else:
            setattr(args, field, raw_value)

    _assert_required_args(args, required)
    log(
        'input_merge_result',
        {field: getattr(args, field, None) for field in sorted(set(required + list_fields))},
    )
    return args


def _first_csv_row(path: Path) -> dict[str, str] | None:
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        return next(csv.DictReader(handle), None)


def _find_csv_case_insensitive(input_dir: Path, expected_name: str) -> Path | None:
    if not input_dir.is_dir():
        return None

    expected_lower = expected_name.lower()
    for entry in input_dir.iterdir():
        if entry.is_file() and entry.name.lower() == expected_lower:
            return entry
    return None


def _assert_required_args(args: Namespace, required: list[str]) -> None:
    missing = [field for field in required if getattr(args, field, None) in (None, '', [])]
    if missing:
        names = ', '.join(f'--{name.replace("_", "-")}' for name in missing)
        raise ValueError(f'Faltan parámetros requeridos: {names}')
