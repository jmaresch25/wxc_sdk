from __future__ import annotations

from typing import Any

from wxc_sdk.rest import RestError

from .common import create_api, model_to_dict

_FEATURE_ENDPOINTS: dict[tuple[str, str], str] = {
    ('person', 'outgoing_permissions'): 'people/{entity_id}/features/outgoingPermission',
    ('person', 'call_forwarding'): 'telephony/config/people/{entity_id}/callForwarding',
    ('workspace', 'outgoing_permissions'): 'workspaces/{entity_id}/features/outgoingPermission',
    ('workspace', 'call_forwarding'): 'telephony/config/workspaces/{entity_id}/callForwarding',
}


def _is_unauthorized_error(error: RestError) -> bool:
    return error.status_code in {401, 403}


def _is_missing_calling_license_error(error: RestError) -> bool:
    text = f'{error.description or ""} {error.message or ""}'.lower()
    return (
        error.code in {4006, 4012, 4043}
        or 'calling' in text and 'license' in text
        or 'not enabled for calling' in text
        or 'not a calling' in text
    )


def _is_pstn_not_configured_error(error: RestError) -> bool:
    text = f'{error.description or ""} {error.message or ""}'.lower()
    return 'pstn' in text and ('not configured' in text or 'not available' in text or 'missing' in text)


def _params(org_id: str | None) -> dict[str, str] | None:
    return {'orgId': org_id} if org_id else None


def _evaluate_error(error: RestError) -> str:
    if _is_unauthorized_error(error):
        return 'unauthorized_feature'
    if _is_missing_calling_license_error(error):
        return 'missing_calling_license'
    if _is_pstn_not_configured_error(error):
        return 'pstn_not_configured'
    return 'unauthorized_feature'


def run_feature_precheck(
    *,
    token: str,
    org_id: str | None,
    entity_id: str,
    entity_type: str,
    feature_name: str,
) -> dict[str, Any]:
    """Ejecuta validaciones previas de acceso, capacidad calling y disponibilidad de feature."""
    api = create_api(token)
    params = _params(org_id)

    try:
        base_url = api.session.ep('telephony/config/locations')
        api.session.rest_get(url=base_url, params=params)
    except RestError as error:
        reason = _evaluate_error(error)
        return {'ok': False, 'reason': reason, 'stage': 'telephony_base_access', 'error': str(error)}
    except Exception as error:  # noqa: BLE001
        return {'ok': False, 'reason': 'unauthorized_feature', 'stage': 'telephony_base_access', 'error': str(error)}

    calling_endpoint = f'telephony/config/{entity_type}s/{entity_id}'
    try:
        calling_url = api.session.ep(calling_endpoint)
        api.session.rest_get(url=calling_url, params=params)
    except RestError as error:
        reason = _evaluate_error(error)
        return {'ok': False, 'reason': reason, 'stage': 'calling_capability', 'error': str(error)}
    except Exception as error:  # noqa: BLE001
        return {'ok': False, 'reason': 'missing_calling_license', 'stage': 'calling_capability', 'error': str(error)}

    endpoint_template = _FEATURE_ENDPOINTS.get((entity_type, feature_name))
    if endpoint_template is None:
        return {'ok': False, 'reason': 'unauthorized_feature', 'stage': 'feature_availability', 'error': f'feature_not_supported:{feature_name}'}

    feature_endpoint = endpoint_template.format(entity_id=entity_id)
    try:
        feature_url = api.session.ep(feature_endpoint)
        payload = api.session.rest_get(url=feature_url, params=params)
    except RestError as error:
        reason = _evaluate_error(error)
        return {'ok': False, 'reason': reason, 'stage': 'feature_availability', 'error': str(error)}
    except Exception as error:  # noqa: BLE001
        return {'ok': False, 'reason': 'unauthorized_feature', 'stage': 'feature_availability', 'error': str(error)}

    return {
        'ok': True,
        'entity_type': entity_type,
        'feature_name': feature_name,
        'feature_endpoint': feature_endpoint,
        'feature_snapshot': model_to_dict(payload),
    }
