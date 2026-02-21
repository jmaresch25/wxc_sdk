from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import product
from typing import Any

from .common import ModuleResult, as_list, call_with_supported_kwargs, model_to_dict, resolve_attr


STANDARD_COLUMNS = [
    'id',
    'name',
    'first_name',
    'last_name',
    'member_id',
    'member_type',
    'location_id',
    'person_id',
    'workspace_id',
    'license_id',
    'virtual_line_id',
    'group_id',
    'route_group_id',
    'connection_type',
    'language',
    'address_1',
    'city',
    'state',
    'postal_code',
    'country',
    'direct_number',
    'webex_calling_enabled',
    'source_method',
    'raw_keys',
    'raw_json',
]


@dataclass(frozen=True)
class ParamSource:
    name: str
    module: str
    field: str
    required_field: str | None = None


@dataclass(frozen=True)
class ArtifactSpec:
    module: str
    method_path: str
    static_kwargs: dict[str, Any]
    param_sources: tuple[ParamSource, ...] = ()


class ParamSourceValidationError(ValueError):
    """Raised when an artifact cannot run due to missing required source IDs."""


def _build_source_id_diagnostic(cache: dict[str, list[dict]], source: ParamSource) -> dict[str, Any]:
    rows = cache.get(source.module, [])
    values = _id_values(cache, source)
    return {
        'source_module': source.module,
        'param_name': source.name,
        'field': source.field,
        'required_field': source.required_field,
        'min_required': 1,
        'valid_ids_detected': len(values),
        'cache_rows': len(rows),
        'sample_ids': values[:5],
    }


def _id_values(cache: dict[str, list[dict]], source: ParamSource) -> list[Any]:
    rows = cache.get(source.module, [])
    values = [
        r.get(source.field)
        for r in rows
        if r.get(source.field) and (source.required_field is None or r.get(source.required_field))
    ]
    uniq: list[Any] = []
    seen = set()
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        uniq.append(v)
    return uniq


def _iter_kwargs(
    cache: dict[str, list[dict]],
    spec: ArtifactSpec,
    *,
    diagnostics: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not spec.param_sources:
        return [dict(spec.static_kwargs)]
    source_diagnostics = [_build_source_id_diagnostic(cache, src) for src in spec.param_sources]
    value_lists = [_id_values(cache, src) for src in spec.param_sources]
    if any(not vals for vals in value_lists):
        if diagnostics is not None:
            diagnostics.extend(source_diagnostics)
        return []
    if diagnostics is not None:
        diagnostics.extend(source_diagnostics)
    keys = [s.name for s in spec.param_sources]
    out: list[dict[str, Any]] = []
    for combo in product(*value_lists):
        kwargs = dict(spec.static_kwargs)
        kwargs.update(dict(zip(keys, combo)))
        out.append(kwargs)
    return out


def required_source_ids_per_artifact(spec: ArtifactSpec) -> list[dict[str, str | int | None]]:
    if not spec.param_sources:
        return []
    table: list[dict[str, str | int | None]] = []
    for source in spec.param_sources:
        table.append({
            'artifact': spec.module,
            'source_module': source.module,
            'param_name': source.name,
            'field': source.field,
            'required_field': source.required_field,
            'min_required': 1,
        })
    return table


def validate_param_sources(cache: dict[str, list[dict]], spec: ArtifactSpec) -> None:
    diagnostics: list[dict[str, Any]] = []
    _iter_kwargs(cache, spec, diagnostics=diagnostics)
    missing = [d for d in diagnostics if d['valid_ids_detected'] < d['min_required']]
    if not missing:
        return

    requirements = required_source_ids_per_artifact(spec)
    details: list[str] = []
    for item in missing:
        details.append(
            f"{item['source_module']} ({item['field']} -> {item['param_name']}): "
            f"{item['valid_ids_detected']}/{item['min_required']} IDs válidos"
        )
    requirements_json = json.dumps(requirements, ensure_ascii=False, sort_keys=True)
    diagnostics_json = json.dumps(missing, ensure_ascii=False, sort_keys=True)
    raise ParamSourceValidationError(
        f"Artifact '{spec.module}' no ejecutable por IDs fuente insuficientes. "
        f"Detalles: {', '.join(details)}. "
        f"required_source_ids_per_artifact={requirements_json}; "
        f"source_diagnostics={diagnostics_json}"
    )


LOOKUP_METHODS: dict[str, tuple[str, dict[str, Any]]] = {
    'people': ('people.list', {'calling_data': True}),
    'workspaces': ('workspaces.list', {}),
    'calling_locations': ('telephony.locations.list', {}),
    'hunt_groups': ('telephony.huntgroup.list', {}),
    'virtual_lines': ('telephony.virtual_lines.list', {}),
    'virtual_extensions': ('telephony.virtual_extensions.list_extensions', {}),
    'virtual_extension_ranges': ('telephony.virtual_extensions.list_range', {}),
}


def _enrich_lookup_row(module_name: str, raw_item: dict[str, Any]) -> dict[str, Any]:
    row = _canonical_item(raw_item)
    if module_name == 'people':
        if not row.get('person_id'):
            row['person_id'] = row.get('id')
    if module_name == 'workspaces':
        if not row.get('id'):
            row['id'] = row.get('workspace_id')
        if not row.get('workspace_id'):
            row['workspace_id'] = row.get('id')
    return row


def hydrate_lookup_sources(api, spec: ArtifactSpec, cache: dict[str, list[dict]]) -> None:
    for source in spec.param_sources:
        if _id_values(cache, source):
            continue
        lookup = LOOKUP_METHODS.get(source.module)
        if lookup is None:
            continue
        method_path, kwargs = lookup
        try:
            payload = call_with_supported_kwargs(resolve_attr(api, method_path), **kwargs)
        except Exception:
            continue
        rows = [_enrich_lookup_row(source.module, model_to_dict(i)) for i in as_list(payload)]
        if rows:
            cache[source.module] = rows


def _canonical_item(item: dict[str, Any]) -> dict[str, Any]:
    address = item.get('address') if isinstance(item.get('address'), dict) else {}
    calling_data = item.get('calling_data') if isinstance(item.get('calling_data'), dict) else (
        item.get('callingData') if isinstance(item.get('callingData'), dict) else {}
    )
    out = dict(item)

    out.setdefault('id', item.get('id') or item.get('member_id') or item.get('person_id') or item.get('workspace_id'))
    out.setdefault('name', item.get('name') or item.get('displayName') or item.get('display_name'))
    out.setdefault('first_name', item.get('first_name') or item.get('firstName'))
    out.setdefault('last_name', item.get('last_name') or item.get('lastName'))
    out.setdefault('member_id', item.get('member_id') or item.get('memberId') or item.get('id'))
    out.setdefault('member_type', item.get('member_type') or item.get('memberType') or item.get('type'))
    out.setdefault('location_id', item.get('location_id') or item.get('locationId')
                   or calling_data.get('location_id') or calling_data.get('locationId'))
    out.setdefault('person_id', item.get('person_id') or item.get('personId'))
    out.setdefault('workspace_id', item.get('workspace_id') or item.get('workspaceId'))
    out.setdefault('license_id', item.get('license_id') or item.get('licenseId'))
    out.setdefault('virtual_line_id', item.get('virtual_line_id') or item.get('virtualLineId'))
    out.setdefault('group_id', item.get('group_id') or item.get('groupId'))
    out.setdefault('route_group_id', item.get('route_group_id') or item.get('routeGroupId') or item.get('premise_route_id')
                   or item.get('premiseRouteId'))
    out.setdefault('connection_type', item.get('connection_type') or item.get('connectionType')
                   or item.get('pstn_connection_type') or item.get('pstnConnectionType'))
    out.setdefault('language', item.get('language') or item.get('preferredLanguage'))
    out.setdefault('address_1', item.get('address_1') or item.get('address1') or address.get('address1'))
    out.setdefault('city', item.get('city') or address.get('city'))
    out.setdefault('state', item.get('state') or address.get('state'))
    out.setdefault('postal_code', item.get('postal_code') or item.get('postalCode') or address.get('postalCode'))
    out.setdefault('country', item.get('country') or address.get('country'))
    out.setdefault('direct_number', item.get('direct_number') or item.get('directNumber') or item.get('phone_number') or item.get('phoneNumber'))


    member_type = str(out.get('member_type') or '').upper()
    if not out.get('person_id') and member_type in {'PEOPLE', 'PERSON', 'USER'} and out.get('member_id'):
        out['person_id'] = out.get('member_id')
    if not out.get('workspace_id') and member_type in {'WORKSPACE', 'PLACE'} and out.get('member_id'):
        out['workspace_id'] = out.get('member_id')

    if 'webex_calling_enabled' not in out:
        out['webex_calling_enabled'] = bool(out.get('location_id'))

    return out


def _row_from_item(item: dict, method_path: str, kwargs: dict[str, Any]) -> dict:
    canonical = _canonical_item(item)
    row = {k: canonical.get(k, '') for k in STANDARD_COLUMNS}
    for k in ('location_id', 'person_id', 'workspace_id', 'license_id', 'virtual_line_id', 'group_id', 'id', 'name'):
        if not row.get(k) and kwargs.get(k):
            row[k] = kwargs[k]
    for k, v in kwargs.items():
        if k.endswith('_id') and k not in row:
            row[k] = v
    row['source_method'] = method_path
    row['raw_keys'] = ','.join(sorted(item.keys()))
    row['raw_json'] = json.dumps(item, ensure_ascii=False, sort_keys=True)
    return row


def _is_user_access_error(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code == 4003:
        return True
    detail = getattr(exc, "detail", None)
    if detail is not None and getattr(detail, "code", None) == 4003:
        return True
    text = str(exc)
    if '4003' in text and 'Unauthorized request' in text:
        return True
    return False


def run_artifact(api, spec: ArtifactSpec, cache: dict[str, list[dict]]) -> ModuleResult:
    method = resolve_attr(api, spec.method_path)
    rows: list[dict] = []
    hydrate_lookup_sources(api, spec, cache)
    validate_param_sources(cache, spec)
    kwargs_diagnostics: list[dict[str, Any]] = []
    for kwargs in _iter_kwargs(cache, spec, diagnostics=kwargs_diagnostics):
        try:
            payload = call_with_supported_kwargs(method, **kwargs)
        except Exception as exc:
            # Some person-level endpoints return 4003 (unauthorized/user not found)
            # for users without Webex Calling entitlements. Skip these entities and
            # continue with the remaining exportable users.
            if _is_user_access_error(exc):
                continue
            raise
        items = [model_to_dict(i) for i in as_list(payload)]
        if not items and isinstance(payload, object):
            maybe = model_to_dict(payload)
            if maybe:
                items = [maybe]
        for item in items:
            rows.append(_row_from_item(item, spec.method_path, kwargs))
    return ModuleResult(module=spec.module, method=spec.method_path, rows=rows, count=len(rows), raw_keys=[])


V1_ARTIFACT_SPECS: list[ArtifactSpec] = [
    ArtifactSpec('calling_locations', 'telephony.locations.list', {}),
    ArtifactSpec('calling_locations_details', 'telephony.locations.details', {}, (ParamSource('location_id', 'calling_locations', 'id'),)),

    ArtifactSpec('location_details', 'locations.details', {},
                 (ParamSource('location_id', 'locations', 'location_id'),)),
    ArtifactSpec('people_details', 'people.details', {'calling_data': True},
                 (ParamSource('person_id', 'people', 'person_id'),)),
    ArtifactSpec('workspace_details', 'workspaces.details', {},
                 (ParamSource('workspace_id', 'workspaces', 'id'),)),
    ArtifactSpec('location_pstn_connection', 'telephony.pstn.read', {},
                 (ParamSource('location_id', 'calling_locations', 'id'),)),
    ArtifactSpec('person_call_forwarding', 'person_settings.forwarding.read', {},
                 (ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),)),
    ArtifactSpec('workspace_call_forwarding', 'workspace_settings.forwarding.read', {},
                 (ParamSource('entity_id', 'workspaces', 'id'),)),
    ArtifactSpec('group_members', 'groups.members', {}, (ParamSource('group_id', 'groups', 'group_id'),)),
    ArtifactSpec('license_assigned_users', 'licenses.assigned_users', {}, (ParamSource('license_id', 'licenses', 'license_id'),)),
    ArtifactSpec('workspace_capabilities', 'workspaces.capabilities', {}, (ParamSource('workspace_id', 'workspaces', 'id'),)),

    ArtifactSpec('auto_attendants', 'telephony.auto_attendant.list', {}),
    ArtifactSpec('auto_attendant_details', 'telephony.auto_attendant.details', {},
                 (ParamSource('location_id', 'auto_attendants', 'location_id'), ParamSource('auto_attendant_id', 'auto_attendants', 'id'))),
    ArtifactSpec('auto_attendant_announcement_files', 'telephony.auto_attendant.list_announcement_files', {},
                 (ParamSource('location_id', 'auto_attendants', 'location_id'), ParamSource('auto_attendant_id', 'auto_attendants', 'id'))),
    ArtifactSpec('auto_attendant_forwarding', 'telephony.auto_attendant.forwarding.settings', {},
                 (ParamSource('location_id', 'auto_attendants', 'location_id'), ParamSource('auto_attendant_id', 'auto_attendants', 'id'))),

    ArtifactSpec('hunt_groups', 'telephony.huntgroup.list', {}),
    ArtifactSpec('hunt_group_details', 'telephony.huntgroup.details', {},
                 (ParamSource('location_id', 'hunt_groups', 'location_id'), ParamSource('huntgroup_id', 'hunt_groups', 'id'))),
    ArtifactSpec('hunt_group_forwarding', 'telephony.huntgroup.forwarding.settings', {},
                 (ParamSource('location_id', 'hunt_groups', 'location_id'), ParamSource('huntgroup_id', 'hunt_groups', 'id'))),

    ArtifactSpec('call_queues', 'telephony.callqueue.list', {}),
    ArtifactSpec('call_queue_details', 'telephony.callqueue.details', {},
                 (ParamSource('location_id', 'call_queues', 'location_id'), ParamSource('queue_id', 'call_queues', 'id'))),
    ArtifactSpec('call_queue_settings', 'telephony.callqueue.get_call_queue_settings', {},
                 (ParamSource('location_id', 'call_queues', 'location_id'), ParamSource('queue_id', 'call_queues', 'id'))),
    ArtifactSpec('call_queue_agents', 'telephony.callqueue.agents.list', {},
                 (ParamSource('location_id', 'call_queues', 'location_id'), ParamSource('queue_id', 'call_queues', 'id'))),
    ArtifactSpec('call_queue_forwarding', 'telephony.callqueue.forwarding.settings', {},
                 (ParamSource('location_id', 'call_queues', 'location_id'), ParamSource('feature_id', 'call_queues', 'id'))),

    ArtifactSpec('virtual_lines', 'telephony.virtual_lines.list', {}),
    ArtifactSpec('virtual_line_details', 'telephony.virtual_lines.details', {},
                 (ParamSource('virtual_line_id', 'virtual_lines', 'id'),)),
    ArtifactSpec('virtual_line_assigned_devices', 'telephony.virtual_lines.assigned_devices', {},
                 (ParamSource('virtual_line_id', 'virtual_lines', 'id'),)),

    ArtifactSpec('virtual_extensions', 'telephony.virtual_extensions.list_extensions', {}),
    ArtifactSpec('virtual_extension_details', 'telephony.virtual_extensions.details_extension', {},
                 (ParamSource('location_id', 'virtual_extensions', 'location_id'), ParamSource('extension_id', 'virtual_extensions', 'id'))),
    ArtifactSpec('virtual_extension_ranges', 'telephony.virtual_extensions.list_range', {}),
    ArtifactSpec('virtual_extension_range_details', 'telephony.virtual_extensions.details_range', {},
                 (ParamSource('location_id', 'virtual_extension_ranges', 'location_id'), ParamSource('range_id', 'virtual_extension_ranges', 'id'))),

    ArtifactSpec('person_numbers', 'person_settings.numbers.read', {},
                 (ParamSource('person_id', 'people', 'person_id', required_field='location_id'),)),
    ArtifactSpec('person_permissions_in', 'person_settings.permissions_in.read', {},
                 (ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),)),
    ArtifactSpec('person_permissions_out', 'person_settings.permissions_out.read', {},
                 (ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),)),
    ArtifactSpec('person_out_access_codes', 'person_settings.permissions_out.access_codes.read', {},
                 (ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),)),
    ArtifactSpec('person_out_digit_patterns', 'person_settings.permissions_out.digit_patterns.get_digit_patterns', {},
                 (ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),)),
    ArtifactSpec('person_transfer_numbers', 'person_settings.permissions_out.transfer_numbers.read', {},
                 (ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),)),

    ArtifactSpec('workspace_permissions_in', 'workspace_settings.permissions_in.read', {}, (ParamSource('entity_id', 'workspaces', 'id'),)),
    ArtifactSpec('workspace_permissions_out', 'workspace_settings.permissions_out.read', {}, (ParamSource('entity_id', 'workspaces', 'id'),)),
    ArtifactSpec('workspace_numbers', 'workspace_settings.numbers.read', {}, (ParamSource('workspace_id', 'workspaces', 'id'),)),
    ArtifactSpec('workspace_devices', 'workspace_settings.devices.list', {}, (ParamSource('workspace_id', 'workspaces', 'id'),)),

    ArtifactSpec('person_available_numbers_primary', 'person_settings.available_numbers.primary', {}, (ParamSource('location_id', 'people', 'location_id'),)),
    ArtifactSpec('person_available_numbers_secondary', 'person_settings.available_numbers.secondary', {},
                 (ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),)),
    ArtifactSpec('person_available_numbers_call_forward', 'person_settings.available_numbers.call_forward', {},
                 (ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),)),
    ArtifactSpec('person_available_numbers_call_intercept', 'person_settings.available_numbers.call_intercept', {},
                 (ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),)),
    ArtifactSpec('person_available_numbers_ecbn', 'person_settings.available_numbers.ecbn', {},
                 (ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),)),
    ArtifactSpec('person_available_numbers_fax_message', 'person_settings.available_numbers.fax_message', {},
                 (ParamSource('entity_id', 'people', 'person_id', required_field='location_id'),)),

    ArtifactSpec('virtual_line_available_numbers_available', 'telephony.virtual_lines.available_numbers.available', {}, (ParamSource('virtual_line_id', 'virtual_lines', 'id'),)),
    ArtifactSpec('virtual_line_available_numbers_primary', 'telephony.virtual_lines.available_numbers.primary', {}, (ParamSource('virtual_line_id', 'virtual_lines', 'id'),)),
    ArtifactSpec('virtual_line_available_numbers_secondary', 'telephony.virtual_lines.available_numbers.secondary', {}, (ParamSource('virtual_line_id', 'virtual_lines', 'id'),)),

    ArtifactSpec('workspace_available_numbers_available', 'workspace_settings.available_numbers.available', {}, (ParamSource('workspace_id', 'workspaces', 'id'),)),
    ArtifactSpec('workspace_available_numbers_secondary', 'workspace_settings.available_numbers.secondary', {}, (ParamSource('entity_id', 'workspaces', 'id'),)),
]
