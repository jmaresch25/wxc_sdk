from __future__ import annotations

import pytest

from Space_OdT.v21.ui_v211 import (
    _build_params,
    _preview_action,
    ACTION_DESCRIPTIONS,
)


def test_build_params_uses_default_column_when_mapping_missing():
    row = {'location_id': 'loc-1', 'phone_numbers': '+34910000001;+34910000002'}

    params, missing = _build_params('ubicacion_alta_numeraciones_desactivadas', row, mapping={})

    assert missing == []
    assert params['location_id'] == 'loc-1'
    assert params['phone_numbers'] == ['+34910000001', '+34910000002']


def test_preview_rejects_actions_in_development():
    with pytest.raises(ValueError, match='en desarrollo'):
        _preview_action('workspaces_alta', rows=[{}], mapping={})

    assert ACTION_DESCRIPTIONS['workspaces_alta'] == '... en desarrollo ...'


def test_apply_action_bulk_returns_orders(monkeypatch):
    from Space_OdT.v21 import ui_v211

    monkeypatch.setitem(ui_v211.HANDLERS, 'usuarios_modificar_licencias', lambda token, **kwargs: {'status_code': 200, 'payload': kwargs})

    rows = [
        {'person_id': 'p1', 'add_license_ids': 'lic-a;lic-b'},
        {'person_id': 'p2', 'add_license_ids': 'lic-c'},
        {'person_id': 'p3', 'add_license_ids': 'lic-d'},
    ]
    result = ui_v211._apply_action(
        action_id='usuarios_modificar_licencias',
        rows=rows,
        mapping={},
        token='tkn',
        bulk=True,
        chunk_size=2,
        max_workers=2,
    )

    assert result['bulk']['enabled'] is True
    assert result['bulk']['orders_total'] == 2
    assert result['total_rows'] == 3
