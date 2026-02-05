# Module: startup_checks.py

## Purpose
Run pre-flight validation before processing any row.

## Required checks

1. Required env vars present:
   - `WEBEX_TOKEN`, `WEBEX_BASE_URL`, `ENVIRONMENT`
2. Perform minimal API health checks:
   - `locations_list` (or equivalent)
   - `people_me` (or equivalent)
3. If authentication or permissions fail:
   - Abort without processing rows.
   - Log `startup_checks=fail` with reason.

## Logging

- Log `startup_checks=pass` on success.
- Never log secrets.
