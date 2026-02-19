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
