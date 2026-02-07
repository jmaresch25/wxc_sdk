# Module: action_helpers.py

## Purpose
Provide pure helper builders for payload construction and row normalization. This module must remain side-effect free.

## Required behaviors

- Build API payloads from normalized CSV rows.
- Compose `entity_key` if missing (per input schema rules).
- Reject user identity fields (display_name, first_name, last_name, etc.) for any `user_*` entity.
- Normalize phone numbers (e.g., E.164) consistently.
- Provide deterministic mapping between CSV fields and API payloads.

## Constraints

- No network calls.
- No file I/O.
- No logging of secrets.
- Any unsupported field => return marker for `out_of_scope` handling by executor.
