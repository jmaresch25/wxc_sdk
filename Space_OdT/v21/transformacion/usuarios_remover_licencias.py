from __future__ import annotations

"""Script v21 de transformación: remove de licencias de usuario (SDK-first)."""

import argparse
from typing import Any

from .common import apply_csv_arguments, get_token, load_runtime_env
from .usuarios_modificar_licencias import modificar_licencias_usuario

SCRIPT_NAME = 'usuarios_remover_licencias'


def remover_licencias_usuario(
    *,
    token: str,
    person_id: str,
    remove_license_ids: list[str],
    org_id: str | None = None,
) -> dict[str, Any]:
    if not remove_license_ids:
        raise ValueError('remove_license_ids es obligatorio para remover licencias')

    return modificar_licencias_usuario(
        token=token,
        person_id=person_id,
        remove_license_ids=remove_license_ids,
        org_id=org_id,
    )


def main() -> None:
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Remover licencias de usuario (SDK-first)')
    parser.add_argument('--token', default=None)
    parser.add_argument('--csv', default=None, help='CSV con parámetros de entrada (se usa primera fila)')
    parser.add_argument('--person-id', default=None)
    parser.add_argument('--remove-license-id', action='append', default=None, dest='remove_license_ids')
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()
    args = apply_csv_arguments(args, required=['person_id', 'remove_license_ids'], list_fields=['remove_license_ids'])

    payload = remover_licencias_usuario(
        token=get_token(args.token),
        person_id=args.person_id,
        remove_license_ids=args.remove_license_ids,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
