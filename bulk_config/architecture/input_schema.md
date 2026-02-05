# Input Schema (Single CSV Source of Truth)

This document defines the **mandatory, provisional** CSV contract for the Universal Webex Bulk Provision Bot. The schema is authoritative; any row that violates it must be **rejected** pre-API.

## 1. Common columns (all rows)

Required:
- `entity_type` (string): One of the allowed entity types enumerated in this document.
- `entity_key` (string): Stable, deterministic key for lookup/upsert. If omitted in the input, it must be derived (see Section 4).
- `row_ref` (string, optional): External row identifier. If absent, the pipeline assigns a sequential `row_id`.
- `location_key` (string, required when applicable): Location lookup key for entities tied to a location.

## 2. Entity types and phase mapping

Entity types (CSV values) are **internal labels** that map to API actions. The executor enforces the fixed phase order:

### Phase 1 — Location + telephony routing (site-level)
- `location`
- `trunk`
- `route_group`
- `internal_dialing`
- `dial_plan`
- `location_call_profiles`
- `location_number_state`
- `schedules`
- `announcements_repo`

### Phase 2 — Calling config for existing users/workspaces
- `user_calling_settings`
- `user_numbers`
- `user_forwarding`
- `user_recording`
- `user_monitoring`
- `user_exec_assistant`
- `workspace`
- `workspace_numbers`
- `workspace_forwarding`
- `workspace_recording`
- `workspace_monitoring`

### Phase 3 — Shared services & membership constructs
- `groups`
- `group_membership`
- `feature_access`
- `call_pickup_group`
- `call_queue`
- `hunt_group`
- `auto_attendant`
- `devices`
- `number_removal`

## 3. Required columns by entity type

The CSV may include extra columns, but only fields supported by the API are actionable. Unsupported fields result in `pending` with `reason_code=out_of_scope`.

### 3.1 Location (`entity_type=location`)
Required:
- `location_name` (if `location_external_id` missing)
- `time_zone`
- `address_*` (minimum address fields as agreed; missing fields => rejected)
Optional:
- `location_external_id`

### 3.2 Trunk (`entity_type=trunk`)
Required:
- `trunk_name`
- `sbc_address` (or `sip_server`)
- `sip_port`
- `transport`
Optional:
- `authentication_*` (only if API supports it)

### 3.3 Route group (`entity_type=route_group`)
Required:
- `route_group_name`
- `trunk_names` or `trunk_ids` (depending on implementation)

### 3.4 Dial plan / routing (`entity_type=dial_plan`)
Required:
- `rule_name` (or composite fields to derive it)
- `pattern`
- `priority`
- `route_target` (trunk or route group reference)

### 3.5 Internal dialing (`entity_type=internal_dialing`)
Required:
- `route_unknown_extensions` (boolean)
- `route_target` (trunk or route group reference)

### 3.6 User entities (post-LDAP)
Applies to: `user_calling_settings`, `user_numbers`, `user_forwarding`, `user_recording`, `user_monitoring`, `user_exec_assistant`

Required:
- `email`
- `location_key`
Optional:
- `calling_enabled` (default true)
- `calling_settings_*`
- `extension`
- `phone_number` / `phone_number_secondary[]`

**Out-of-scope fields** (reject if present):
- `display_name`, `first_name`, `last_name`, or any identity/profile attributes.

### 3.7 Workspace entities
Applies to: `workspace`, `workspace_numbers`, `workspace_forwarding`, `workspace_recording`, `workspace_monitoring`

Required:
- `workspace_display_name` or `workspace_external_id`
- `location_key`
Optional:
- `extension`
- `phone_number` / `phone_number_secondary[]`

### 3.8 Shared services
- `groups`: `group_name` (required)
- `group_membership`: `group_name`, `member_email` (or member ids)
- `feature_access`: `email`, feature flags supported by API
- `call_pickup_group`: `group_name`, `extension`, `members[]`
- `call_queue`: `queue_name`, `extension_or_number`, `agents[]`, `language`
- `hunt_group`: `hunt_group_name`, `extension_or_number`, `members[]`, `routing_policy`
- `auto_attendant`: `aa_name`, `extension_or_number`, schedules/menus/greetings references
- `devices`: `person_email` or `workspace_display_name`, `device_model` or `serial/mac`
- `number_removal`: `phone_number` (E.164) + `location_key`

## 4. Entity key derivation (deterministic)

If `entity_key` is absent or blank, it must be derived as follows:
- `location`: `location_external_id` else `location_name`
- `trunk`: `trunk_name`
- `route_group`: `route_group_name`
- `dial_plan`: `rule_name` or composite `location_id + priority + pattern`
- `user_*`: `email`
- `workspace`: `workspace_display_name` or `workspace_external_id`
- `assignment/numbers`: composite `(location_id + extension)` or `(location_id + phone_number)`
- `call_queue`/`hunt_group`/`auto_attendant`/`call_pickup_group`: composite `(location_id + name/extension)`
- `devices`: `serial`/`mac` if present; otherwise a composite of target + model

## 5. Pre-API validation rules (reject on failure)

- `entity_type` is in the allowed enumeration.
- `email` format is valid for user entities.
- `location_key` is present when required.
- `extension` is numeric, 2–8 digits.
- `phone_number` must match agreed format (E.164 if required).
- CSV uniqueness rules:
  - `location_key` is unique for `location` rows.
  - `email` is unique for user rows where uniqueness is required.
  - `extension` is unique per `location_key` when assignments are used.

## 6. Rejection output (pre-API)

Any row that fails these rules must be written to `rejected_rows.csv` with:
`reason_code=invalid_input_schema` or `duplicate_key` and an explicit message.
