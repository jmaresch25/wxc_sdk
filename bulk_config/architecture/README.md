# Universal Webex Bulk Provision Bot — Architecture (Post-LDAP)

This folder provides the architecture-only blueprint for implementing the Universal Webex Bulk Provision Bot. No runtime code is included; each file defines the requirements, responsibilities, and constraints for the corresponding module or contract.

## Step-by-step structure

1. **Contracts and schemas**
   - `input_schema.md`: single CSV contract (columns, validation, and scope rules).
   - `output_contract.md`: output artifacts (`results.csv`, `pending_rows.csv`, `rejected_rows.csv`, `checkpoint.json`).

2. **Pipeline modules (requirements only)**
   - `modules/config.md`
   - `modules/data_pipeline.md`
   - `modules/batch_iterator.md`
   - `modules/connection_client.md`
   - `modules/actions_registry.md`
   - `modules/action_helpers.md`
   - `modules/executor.md`
   - `modules/error_handling.md`
   - `modules/writers.md`
   - `modules/state_store.md`
   - `modules/startup_checks.md`

3. **Operational guarantees**
   - `runtime_guarantees.md`: phases, idempotency, retries/timeouts, circuit breaker, and restart semantics.

## Scope guardrails (non-negotiable)

- Post-LDAP only: users already exist in Webex; the bot **never** creates or updates identity attributes.
- Single CSV input (source of truth). Re-runs must not duplicate resources.
- Every row ends **exactly** as `rejected` (pre-API), `pending` (runtime), or `success`.
- Any missing API/SDK method is **out-of-scope** and must produce `pending` with reason `sdk_method_missing`.
- No secrets in logs.

Refer to each module file for the exact instructions and acceptance criteria.
