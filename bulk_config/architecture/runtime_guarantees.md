# Runtime Guarantees & Execution Model

This file consolidates the operational invariants required by the term sheet.

## 1. Phases (fixed order)

1. Phase 1: Location + routing layer (`location`, `trunk`, `route_group`, `internal_dialing`, `dial_plan`, `location_call_profiles`, `location_number_state`, `schedules`, `announcements_repo`)
2. Phase 2: Existing users/workspaces (`user_*`, `workspace_*`)
3. Phase 3: Shared services (`groups`, `group_membership`, `feature_access`, `call_pickup_group`, `call_queue`, `hunt_group`, `auto_attendant`, `devices`, `number_removal`)

## 2. Idempotency

- Every row must do a remote lookup by stable key before any create/update.
- Create is only allowed for **creatable** entities (e.g., `location`, `trunk`, `route_group`, `workspace`).
- **Users are never created**. Missing user lookup yields `pending` with `reason_code=user_not_found`.
- Upsert is deterministic; no diff computation.

## 3. Batching and limits (static)

- `BATCH_SIZE` default 500
- `MAX_ROWS` default 21000
- `MAX_BATCHES` default `ceil(MAX_ROWS / BATCH_SIZE)` with optional hard cap 1000
- No loop may exceed the configured limits.
- Exceeding a limit triggers controlled exit + checkpoint.

## 4. Retry & timeout policy

- Request timeout: 20 seconds (connect timeout 5 seconds if applicable).
- Retry only on 429, 5xx, timeouts, or network errors.
- Max retries: 5 (exponential backoff + jitter).
- Retry exhaustion => `pending` with `reason_code=retry_exhausted`.

## 5. Startup checks (pre-flight)

- Env vars required: `WEBEX_TOKEN`, `WEBEX_BASE_URL`, `ENVIRONMENT` (lab|prod).
- Perform 1–2 cheap GETs:
  - `locations_list` (or equivalent)
  - `people_me` (token validation)
- If auth/permission fails => abort without processing rows.

## 6. Circuit breaker

- Evaluate after each batch per phase.
- If (`non_retryable_external` + `auth_invalid` + `permission_denied`) >= 80% of batch rows:
  - Abort run.
  - Persist checkpoint to last completed batch.
  - Emit critical log with counts per reason.

## 7. Row termination guarantee

Every input row must end **exactly** as:
- `rejected` (pre-API validation)
- `pending` (runtime failure or out-of-scope)
- `success` (all required steps complete)

## 8. Half-applied handling

If a row performs some steps successfully and later fails:
- Mark `pending` with `reason_code=half_applied`.
- Re-run completes via lookup+upsert; no rollback required by default.

## 9. Logging guardrails

- Structured logging (JSON or key=value).
- Log start/end of run, phase, and batch summaries.
- Log per-row failures once, plus batch summary of reason codes.
- Never log tokens or sensitive headers.
