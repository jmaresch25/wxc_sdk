from __future__ import annotations

"""Asigna usuarios a locations leyendo un CSV generado desde artifacts."""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ''}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from wxc_sdk.licenses import LicenseProperties, LicenseRequest, LicenseRequestOperation

if __package__ in {None, ''}:
    from Space_OdT.v21.transformacion.common import action_logger, create_api, get_token, load_runtime_env, model_to_dict
else:
    from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'usuarios_asignar_location_desde_csv'
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_USERS_EXPORT = REPO_ROOT / '.artifacts' / 'exports' / 'people.json'
DEFAULT_REPORT_CSV = REPO_ROOT / '.artifacts' / 'report' / 'people_to_location.csv'

CSV_HEADERS = [
    'selected',
    'person_id',
    'target_location_id',
]


def _load_people(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(payload, dict):
        items = payload.get('items')
        if isinstance(items, list):
            return items
        raise ValueError(f'Formato no soportado en {path}: se esperaba lista en "items"')
    if isinstance(payload, list):
        return payload
    raise ValueError(f'Formato no soportado en {path}: se esperaba lista JSON')


def _is_truthy(raw: str | None) -> bool:
    return (raw or '').strip().lower() in {'1', 'true', 'yes', 'y', 'si', 'sí', 'x'}


def generate_csv_from_people_json(*, people_json: Path, output_csv: Path, overwrite: bool = False) -> Path:
    if output_csv.exists() and not overwrite:
        return output_csv

    people = _load_people(people_json)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for person in people:
            writer.writerow(
                {
                    'selected': '',
                    'person_id': (person.get('person_id') or person.get('id') or '').strip(),
                    'target_location_id': '',
                }
            )
    return output_csv


def _load_selected_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))

    selected = [row for row in rows if _is_truthy(row.get('selected'))]
    invalid = [
        row
        for row in selected
        if not (row.get('person_id') or '').strip() or not (row.get('target_location_id') or '').strip()
    ]
    if invalid:
        raise ValueError('Hay filas seleccionadas sin person_id o target_location_id')
    return selected


def _phone_number_value(person: Any) -> str | None:
    phone_numbers = getattr(person, 'phone_numbers', None) or []
    for number in phone_numbers:
        value = getattr(number, 'value', None)
        if value and str(value).startswith('+'):
            return str(value)
    return None


def _calling_license_id_for_person(*, api: Any, person: Any) -> str | None:
    person_licenses = set(getattr(person, 'licenses', None) or [])
    if not person_licenses:
        return None

    cache_name = '_calling_license_id_cache'
    calling_license_ids: set[str] | None = getattr(api, cache_name, None)
    if calling_license_ids is None:
        calling_license_ids = {lic.license_id for lic in api.licenses.list() if lic.webex_calling}
        setattr(api, cache_name, calling_license_ids)

    return next((lic_id for lic_id in person_licenses if lic_id in calling_license_ids), None)


def _apply_with_license_assignment(api: Any, row: dict[str, str], person: Any, calling_license_id: str) -> dict[str, Any]:
    person_id = row['person_id'].strip()
    target_location_id = row['target_location_id'].strip()
    extension = (getattr(person, 'extension', None) or '').strip() or None
    phone_number = _phone_number_value(person)
    props = LicenseProperties(location_id=target_location_id, extension=extension, phone_number=phone_number)
    license_request = LicenseRequest(id=calling_license_id, operation=LicenseRequestOperation.add, properties=props)

    response = api.licenses.assign_licenses_to_users(person_id=person_id, licenses=[license_request])
    return {
        'person_id': person_id,
        'from_location_id': getattr(person, 'location_id', None),
        'to_location_id': target_location_id,
        'path': 'licenses.assign_licenses_to_users',
        'calling_license_id': calling_license_id,
        'api_response': model_to_dict(response),
        'status': 'updated',
    }


def _apply_with_people_update(api: Any, row: dict[str, str], person: Any) -> dict[str, Any]:
    """Asigna location usando update del recurso people (campos mínimos obligatorios)."""
    person_id = row['person_id'].strip()
    target_location_id = row['target_location_id'].strip()

    before_location_id = person.location_id
    person.location_id = target_location_id
    updated = api.people.update(person=person, calling_data=True)

    return {
        'person_id': person_id,
        'from_location_id': before_location_id,
        'to_location_id': target_location_id,
        'updated_location_id': updated.location_id,
        'path': 'people.update',
        'status': 'updated',
    }


def _apply_location_change(api: Any, row: dict[str, str]) -> dict[str, Any]:
    person_id = row['person_id'].strip()
    person = api.people.details(person_id=person_id, calling_data=True)
    calling_license_id = _calling_license_id_for_person(api=api, person=person)
    if calling_license_id:
        return _apply_with_license_assignment(api, row, person, calling_license_id)
    return _apply_with_people_update(api, row, person)


def assign_users_to_locations(*, csv_path: Path, token: str | None = None, dry_run: bool = True) -> list[dict[str, Any]]:
    rows = _load_selected_rows(csv_path)
    if not rows:
        print(f'No hay filas seleccionadas en {csv_path}. Marca selected=1 para aplicar cambios.')
        return []

    if dry_run:
        preview = []
        for row in rows:
            preview.append(
                {
                    'person_id': row['person_id'].strip(),
                    'to_location_id': row['target_location_id'].strip(),
                    'sdk_path': 'people.update_or_licenses.assign_licenses_to_users',
                }
            )
        print(json.dumps({'dry_run': True, 'changes': preview}, indent=2, ensure_ascii=False))
        return preview

    load_runtime_env()
    api = create_api(get_token(token))
    log = action_logger(SCRIPT_NAME)
    results: list[dict[str, Any]] = []
    for row in rows:
        payload = _apply_location_change(api, row)
        log('user_location_updated', payload)
        results.append(payload)

    print(json.dumps({'dry_run': False, 'updated': len(results), 'results': model_to_dict(results)}, indent=2, ensure_ascii=False))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description='Asigna usuarios seleccionados en CSV a una location objetivo')
    parser.add_argument('--people-json', type=Path, default=DEFAULT_USERS_EXPORT, help='Export de personas (JSON), solo para generar CSV inicial')
    parser.add_argument('--csv', type=Path, default=DEFAULT_REPORT_CSV, help='CSV de control para selección/mapeo')
    parser.add_argument('--token', default=None)
    parser.add_argument('--overwrite-csv', action='store_true', help='Sobrescribe CSV aunque ya exista')
    parser.add_argument('--generate-only', action='store_true', help='Solo genera el CSV y termina')
    parser.add_argument('--apply', action='store_true', help='Aplica cambios reales (sin este flag se hace dry-run)')
    args = parser.parse_args()

    should_generate_csv = args.generate_only or args.overwrite_csv or not args.csv.exists()
    if should_generate_csv:
        csv_path = generate_csv_from_people_json(
            people_json=args.people_json,
            output_csv=args.csv,
            overwrite=args.overwrite_csv,
        )
    else:
        csv_path = args.csv
    print(f'CSV disponible en: {csv_path}')

    if args.generate_only:
        return

    assign_users_to_locations(csv_path=csv_path, token=args.token, dry_run=not args.apply)


if __name__ == '__main__':
    main()
