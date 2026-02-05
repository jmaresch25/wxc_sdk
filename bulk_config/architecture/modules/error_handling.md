# Module: error_handling.py

## Purpose
Map HTTP responses, SDK errors, and runtime exceptions into standardized `reason_code` values.

## Error classes

- `RETRYABLE_EXTERNAL`: 429, 5xx, network/timeout
- `NON_RETRYABLE_EXTERNAL`: 4xx (permission/contract issues)
- `ASSERTION_FAILURE`: invariant violations
- `UNHANDLED_EXCEPTION`: unexpected runtime errors

## Required reason codes

Base model:
- `invalid_input_schema`
- `duplicate_key`
- `out_of_scope`
- `non_retryable_external`
- `permission_denied`
- `auth_invalid`
- `retry_exhausted`
- `invalid_response_schema`
- `half_applied`
- `unhandled_exception`
- `user_not_found`
- `precondition_missing`

Post-LDAP extensions:
- `workspace_not_found`
- `number_inventory_missing`
- `license_or_feature_missing`
- `resource_dependency_missing`
- `invalid_dial_plan_collision`
- `sdk_method_missing`

## Mapping rules

- Retryable errors exhausted => `retry_exhausted`.
- 401/403 => `auth_invalid` or `permission_denied`.
- Other non-retryable 4xx => `non_retryable_external`.
- Assertion/invariant failures => `half_applied` if any step succeeded; otherwise `unhandled_exception`.
- Missing user/workspace => `user_not_found` or `workspace_not_found`.
- Missing dependencies => `resource_dependency_missing`.
- Precheck failure for license/feature => `license_or_feature_missing`.
- Missing number in inventory => `number_inventory_missing`.
