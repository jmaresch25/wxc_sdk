# Module: connection_client.py

## Purpose
Provide a single HTTP request entry point with timeouts, retries, and response validation.

## Required behaviors

- Apply request and connect timeouts.
- Retry only on retryable errors (429, 5xx, network, timeouts).
- Max retries from config; exponential backoff with jitter.
- Parse JSON responses; validate minimal schema per step definition.
- Map errors to `reason_code` (see `error_handling.md`).

## Step success validation

Each action step must define:
- Allowed HTTP status codes (e.g., 200/201 for create).
- Required response fields (e.g., `id`).

If HTTP status is "ok" but required fields are missing:
- Mark `pending` with `reason_code=invalid_response_schema`.

## Out-of-scope

If the SDK lacks the required method and no REST fallback exists:
- Return `pending` with `reason_code=sdk_method_missing`.
