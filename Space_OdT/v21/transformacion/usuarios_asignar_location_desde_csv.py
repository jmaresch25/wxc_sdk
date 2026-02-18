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
DEFAULT_REPORT_CSV = REPO_ROOT / '.arifacts' / 'report' / 'people_to_location.csv'

CSV_HEADERS = [
    'selected',
    'target_location_id',
    'person_id',
    'email',
    'display_name',
    'current_location_id',
    'calling_license_id',
    'extension',
    'phone_number',
    'org_id',
    'status',
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


def _clean(raw: str | None) -> str | None:
    value = (raw or '').strip()
    return value or None


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
                    'target_location_id': '',
                    'person_id': (person.get('person_id') or person.get('id') or '').strip(),
                    'email': (person.get('email') or '').strip(),
                    'display_name': (person.get('display_name') or person.get('displayName') or '').strip(),
                    'current_location_id': (person.get('location_id') or person.get('locationId') or '').strip(),
                    'calling_license_id': '',
                    'extension': '',
                    'phone_number': '',
                    'org_id': (person.get('org_id') or person.get('orgId') or '').strip(),
                    'status': (person.get('status') or '').strip(),
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


def _apply_with_license_assignment(api: Any, row: dict[str, str]) -> dict[str, Any]:
    """Ruta preferida SDK: asignar licencia de calling con propiedades de location."""
    person_id = row['person_id'].strip()
    target_location_id = row['target_location_id'].strip()
    calling_license_id = (row.get('calling_license_id') or '').strip()
    if not calling_license_id:
        raise ValueError('calling_license_id es obligatorio para asignación por licencias')

    props = LicenseProperties(
        location_id=target_location_id,
        extension=_clean(row.get('extension')),
        phone_number=_clean(row.get('phone_number')),
    )
    license_request = LicenseRequest(id=calling_license_id, operation=LicenseRequestOperation.add, properties=props)

    response = api.licenses.assign_licenses_to_users(
        person_id=person_id,
        licenses=[license_request],
        org_id=_clean(row.get('org_id')),
    )
    return {
        'person_id': person_id,
        'email': (row.get('email') or '').strip(),
        'from_location_id': _clean(row.get('current_location_id')),
        'to_location_id': target_location_id,
        'path': 'licenses.assign_licenses_to_users',
        'api_response': model_to_dict(response),
        'status': 'updated',
    }


def _apply_with_people_update(api: Any, row: dict[str, str]) -> dict[str, Any]:
    """Fallback SDK: update del recurso people cuando no se aporta licencia."""
    person_id = row['person_id'].strip()
    target_location_id = row['target_location_id'].strip()

    person = api.people.details(person_id=person_id, calling_data=True)
    before_location_id = person.location_id
    person.location_id = target_location_id
    updated = api.people.update(person=person, calling_data=True)

    return {
        'person_id': person_id,
        'email': (row.get('email') or '').strip(),
        'from_location_id': before_location_id,
        'to_location_id': target_location_id,
        'updated_location_id': updated.location_id,
        'path': 'people.update',
        'status': 'updated',
    }


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
                    'email': (row.get('email') or '').strip(),
                    'from_location_id': _clean(row.get('current_location_id')),
                    'to_location_id': row['target_location_id'].strip(),
                    'preferred_sdk_path': (
                        'licenses.assign_licenses_to_users'
                        if (row.get('calling_license_id') or '').strip()
                        else 'people.update'
                    ),
                }
            )
        print(json.dumps({'dry_run': True, 'changes': preview}, indent=2, ensure_ascii=False))
        return preview

    load_runtime_env()
    api = create_api(get_token(token))
    log = action_logger(SCRIPT_NAME)
    results: list[dict[str, Any]] = []
    for row in rows:
        if (row.get('calling_license_id') or '').strip():
            payload = _apply_with_license_assignment(api, row)
        else:
            payload = _apply_with_people_update(api, row)
        log('user_location_updated', payload)
        results.append(payload)

    print(json.dumps({'dry_run': False, 'updated': len(results), 'results': model_to_dict(results)}, indent=2, ensure_ascii=False))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description='Asigna usuarios seleccionados en CSV a una location objetivo')
    parser.add_argument('--people-json', type=Path, default=DEFAULT_USERS_EXPORT, help='Export de personas (JSON)')
    parser.add_argument('--csv', type=Path, default=DEFAULT_REPORT_CSV, help='CSV de control para selección/mapeo')
    parser.add_argument('--token', default=None)
    parser.add_argument('--overwrite-csv', action='store_true', help='Sobrescribe CSV aunque ya exista')
    parser.add_argument('--generate-only', action='store_true', help='Solo genera el CSV y termina')
    parser.add_argument('--apply', action='store_true', help='Aplica cambios reales (sin este flag se hace dry-run)')
    args = parser.parse_args()

    csv_path = generate_csv_from_people_json(
        people_json=args.people_json,
        output_csv=args.csv,
        overwrite=args.overwrite_csv,
    )
    print(f'CSV disponible en: {csv_path}')

    if args.generate_only:
        return

    assign_users_to_locations(csv_path=csv_path, token=args.token, dry_run=not args.apply)


if __name__ == '__main__':
    main()
