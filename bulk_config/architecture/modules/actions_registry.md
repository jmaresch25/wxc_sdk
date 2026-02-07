# Module: actions_registry.py

## Purpose
Define the action steps per `entity_type` and per phase. Each step declares:
- HTTP success codes
- Required response fields
- Prechecks (if required)
- Failure mapping to `reason_code`

## Global rules

- `user_create` and `user_update_identity` are **forbidden**.
- Missing SDK method => `pending` with `reason_code=sdk_method_missing`.
- If a precheck cannot be performed via API => `pending` with `reason_code=out_of_scope`.
- Lookup-by-key is mandatory before any create/update.

## Phase 1 — Location & routing

### `location`
Steps:
1. `location_lookup`
2. `location_create` or `location_update`

### `trunk`
Steps:
1. `trunk_lookup`
2. `trunk_create` or `trunk_update`

### `route_group`
Steps:
1. `route_group_lookup`
2. `route_group_create` or `route_group_update`

### `internal_dialing`
Steps:
1. `location_lookup` (ensure location exists)
2. `internal_dialing_update`
Prechecks:
- `route_group_id` or `trunk_id` must exist; otherwise `pending(resource_dependency_missing)`.

### `dial_plan`
Steps:
1. `dial_plan_lookup`
2. `dial_plan_create` or `dial_plan_update`
Prechecks:
- Patterns must not collide with internal extension ranges; collision => `pending(invalid_dial_plan_collision)`.
- `route_group_id`/`trunk_id` must exist; otherwise `pending(resource_dependency_missing)`.

### `location_call_profiles`
Steps:
1. `location_lookup`
2. `location_update_call_profile`

### `location_number_state`
Steps:
1. `location_lookup`
2. `location_manage_number_state`
Prechecks:
- If activation required, validate via API; otherwise `pending(out_of_scope)`.

### `schedules`
Steps:
1. `schedule_lookup`
2. `schedule_create` or `schedule_update`

### `announcements_repo`
Steps:
1. `announcement_lookup` (if available)
2. `announcement_upload`

## Phase 2 — Users & workspaces (post-LDAP)

### `user_calling_settings`
Steps:
1. `user_lookup` (by email)
2. `user_enable_calling` (if `calling_enabled=true`)
3. `user_apply_calling_settings` (if settings provided)
Failure:
- Missing user => `pending(user_not_found)`.

### `user_numbers`
Steps:
1. `user_lookup`
2. `numbers_precheck` (inventory)
3. `user_update_numbers`
Failure:
- Missing user => `pending(user_not_found)`.
- Number missing => `pending(number_inventory_missing)`.

### `user_forwarding`
Steps:
1. `user_lookup`
2. `user_forwarding_configure`

### `user_recording`
Steps:
1. `user_lookup`
2. `recording_precheck`
3. `user_recording_update`
Failure:
- Missing feature/license => `pending(license_or_feature_missing)`.

### `user_monitoring`
Steps:
1. `user_lookup`
2. `monitoring_precheck`
3. `user_monitoring_update`

### `user_exec_assistant`
Steps:
1. `user_lookup` (executive)
2. `assistant_lookups`
3. `exec_assistant_update`

### `workspace`
Steps:
1. `workspace_lookup`
2. `workspace_create` or `workspace_update`

### `workspace_numbers`
Steps:
1. `workspace_lookup`
2. `numbers_precheck`
3. `workspace_update_numbers`
Failure:
- Missing workspace => `pending(workspace_not_found)`.
- Number missing => `pending(number_inventory_missing)`.

### `workspace_forwarding`
Steps:
1. `workspace_lookup`
2. `workspace_forwarding_configure`

### `workspace_recording`
Steps:
1. `workspace_lookup`
2. `recording_precheck`
3. `workspace_recording_update`

### `workspace_monitoring`
Steps:
1. `workspace_lookup`
2. `workspace_monitoring_update`

## Phase 3 — Shared services & membership

### `groups`
Steps:
1. `group_lookup`
2. `group_create` or `group_update`

### `group_membership`
Steps:
1. `group_lookup`
2. `member_lookup`
3. `membership_add` or `membership_remove`

### `feature_access`
Steps:
1. `user_lookup`
2. `feature_access_update`

### `call_pickup_group`
Steps:
1. `call_pickup_lookup`
2. `call_pickup_create` or `call_pickup_update`

### `call_queue`
Steps:
1. `call_queue_lookup`
2. `announcement_upload` (if applicable)
3. `call_queue_create` or `call_queue_update`
4. `call_queue_agents_update` (idempotent)

### `hunt_group`
Steps:
1. `hunt_group_lookup`
2. `hunt_group_create` or `hunt_group_update`

### `auto_attendant`
Steps:
1. `schedule_lookup`/`schedule_create`
2. `announcement_upload` (if applicable)
3. `auto_attendant_lookup`
4. `auto_attendant_create` or `auto_attendant_update`

### `devices`
Steps:
1. `device_lookup` (serial/mac)
2. `device_create` or `device_assign`
3. `device_activation_code` (if required)

### `number_removal`
Steps:
1. `number_precheck_unassigned`
2. `number_remove`
Failure:
- Precheck fails => `pending(number_inventory_missing)` or `pending(precondition_missing)` as applicable.
