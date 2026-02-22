from __future__ import annotations

import argparse
import csv
import json
import logging
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from .common import get_token, load_runtime_env
from .launcher_csv_dependencias import HANDLERS, LOCAL_SCRIPT_DEPENDENCIES, SCRIPT_DEPENDENCIES, _run_script

LOGGER = logging.getLogger(__name__)
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SINGLE_CSV = PACKAGE_ROOT / '.artifacts' / 'report' / 'results_manual.csv'
DEFAULT_BULK_DIR = PACKAGE_ROOT / 'input_data'
DEFAULT_LOG_PATH = PACKAGE_ROOT / '.artifacts' / 'logs' / 'launcher_v2_troubleshooting.log'


@dataclass(frozen=True)
class ScriptSpec:
    key: str
    display_name: str
    supports_single: bool
    supports_bulk: bool


def _build_catalog() -> list[ScriptSpec]:
    return [
        ScriptSpec(key=name, display_name=name, supports_single=True, supports_bulk=True)
        for name in sorted(HANDLERS.keys())
    ]


SCRIPT_CATALOG = _build_catalog()
SCRIPT_BY_KEY = {item.key: item for item in SCRIPT_CATALOG}


def _setup_logging(log_path: Path = DEFAULT_LOG_PATH) -> Path:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_path, maxBytes=512_000, backupCount=2, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return log_path


def _normalize_csv_name(path: Path) -> str:
    return path.name.lower()


def _find_csv_case_insensitive(directory: Path, name: str) -> Path:
    expected = name.lower()
    for csv_path in directory.glob('*.csv'):
        if _normalize_csv_name(csv_path) == expected:
            return csv_path
    return directory / name


def _required_csv_for_script(script_name: str) -> list[str]:
    required = LOCAL_SCRIPT_DEPENDENCIES.get(script_name, SCRIPT_DEPENDENCIES.get(script_name, []))
    csv_names: set[str] = set()
    if script_name.startswith('ubicacion_'):
        csv_names.add('Ubicaciones.csv')
    if script_name.startswith('usuarios_'):
        csv_names.add('Usuarios.csv')
    if script_name.startswith('workspaces_'):
        csv_names.add('Workspaces.csv')
    if 'org_id' in required:
        csv_names.add('Global.csv')
    return sorted(csv_names)


def _csv_has_data(csv_path: Path) -> bool:
    with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        return any(True for _ in reader)


def resolve_input_paths(script_name: str, mode: str, *, single_csv: Path = DEFAULT_SINGLE_CSV, bulk_dir: Path = DEFAULT_BULK_DIR) -> list[Path]:
    if mode == 'single':
        return [single_csv]
    if mode != 'bulk':
        raise ValueError(f'modo no soportado: {mode}')
    names = _required_csv_for_script(script_name)
    return [_find_csv_case_insensitive(bulk_dir, name) for name in names]


def validate_input_files(paths: list[Path]) -> tuple[bool, str | None]:
    for path in paths:
        if not path.exists():
            return False, f'CSV faltante: {path}'
        if path.suffix.lower() == '.csv' and not _csv_has_data(path):
            return False, f'CSV vacío: {path}'
    return True, None


def _print_menu() -> dict[str, str]:
    print('=== Space_OdT Launcher V2 ===')
    letter_map: dict[str, str] = {}
    for index, spec in enumerate(SCRIPT_CATALOG):
        letter = chr(ord('a') + index)
        letter_map[letter] = spec.key
        print(f'{letter}) {spec.display_name}')
    return letter_map


def _choose_script(interactive: bool, cli_script: str | None) -> str:
    if cli_script:
        if cli_script not in SCRIPT_BY_KEY:
            raise ValueError(f'script no permitido: {cli_script}')
        return cli_script

    letter_map = _print_menu()
    if not interactive:
        raise ValueError('se requiere --script en modo no interactivo')

    raw = input(f'Selecciona script [{"..".join(["a", chr(ord("a") + len(SCRIPT_CATALOG) - 1)])}]: ').strip().lower()
    if raw not in letter_map:
        raise ValueError(f'selección inválida: {raw}')
    return letter_map[raw]


def _choose_mode(*, interactive: bool, cli_mode: str | None, spec: ScriptSpec) -> str:
    mode = cli_mode
    if mode is None and interactive:
        mode_raw = input('Modo: 1) single (results_manual.csv)  2) bulk (input_data)\nSelecciona modo [1/2]: ').strip()
        mode = {'1': 'single', '2': 'bulk'}.get(mode_raw)
    if mode not in {'single', 'bulk'}:
        raise ValueError(f'modo inválido: {mode}')
    if mode == 'single' and not spec.supports_single:
        raise ValueError(f'script {spec.key} no soporta modo single')
    if mode == 'bulk' and not spec.supports_bulk:
        raise ValueError(f'script {spec.key} no soporta modo bulk')
    return mode


def run_launcher_v2(*, script_name: str, mode: str, token: str, auto_confirm: bool, single_csv: Path = DEFAULT_SINGLE_CSV, bulk_dir: Path = DEFAULT_BULK_DIR) -> dict[str, Any]:
    csv_paths = resolve_input_paths(script_name, mode, single_csv=single_csv, bulk_dir=bulk_dir)
    ok, validation_error = validate_input_files(csv_paths)
    if not ok:
        return {'status': 'error', 'reason': validation_error, 'script_name': script_name, 'mode': mode}

    LOGGER.info('Validando dependencias...')
    parameter_map = {'csv_path': str(single_csv)} if mode == 'single' else {}
    LOGGER.info('Ejecutando script=%s modo=%s csv=%s', script_name, mode, [str(p) for p in csv_paths])
    result = _run_script(
        script_name=script_name,
        parameter_map=parameter_map,
        token=token,
        auto_confirm=auto_confirm,
        dry_run=False,
    )
    return {'status': 'ok', 'script_name': script_name, 'mode': mode, 'csv_paths': [str(p) for p in csv_paths], 'result': result}


def main() -> None:
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Launcher V2 para scripts de transformación (single/bulk)')
    parser.add_argument('--script', help='Nombre exacto del script a ejecutar')
    parser.add_argument('--mode', choices=['single', 'bulk'])
    parser.add_argument('--token', default=None)
    parser.add_argument('--auto-confirm', action='store_true')
    parser.add_argument('--single-csv', type=Path, default=DEFAULT_SINGLE_CSV)
    parser.add_argument('--bulk-dir', type=Path, default=DEFAULT_BULK_DIR)
    parser.add_argument('--non-interactive', action='store_true')
    args = parser.parse_args()

    log_path = _setup_logging()
    interactive = not args.non_interactive
    script_name = _choose_script(interactive=interactive, cli_script=args.script)
    spec = SCRIPT_BY_KEY[script_name]
    mode = _choose_mode(interactive=interactive, cli_mode=args.mode, spec=spec)

    print(f'Resumen: script={script_name}, modo={mode}')
    csv_paths = resolve_input_paths(script_name, mode, single_csv=args.single_csv, bulk_dir=args.bulk_dir)
    print('CSV detectados:', ', '.join(str(path) for path in csv_paths))
    if interactive and not args.auto_confirm:
        if input('¿Confirmar ejecución? [s/N]: ').strip().lower() not in {'s', 'si', 'y', 'yes'}:
            print('Cancelado por usuario')
            return

    token = get_token(args.token)
    outcome = run_launcher_v2(
        script_name=script_name,
        mode=mode,
        token=token,
        auto_confirm=True,
        single_csv=args.single_csv,
        bulk_dir=args.bulk_dir,
    )
    print(json.dumps({**outcome, 'log_path': str(log_path)}, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
