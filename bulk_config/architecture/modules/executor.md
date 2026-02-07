# Module: executor.py

## Purpose
Orchestrate phases, batches, rows, and steps with restart safety.

## Required behaviors

- Process phases in fixed order (1 → 2 → 3).
- Within a phase, process only the mapped entity types.
- For each row:
  - Execute steps sequentially.
  - Persist row result immediately (results/pending) before moving on.
  - Write checkpoint only after output persistence.
- Continue-on-error: any row failure yields `pending` and execution continues.

## Half-applied handling

If a row succeeds at least one step and then fails:
- Mark `pending` with `reason_code=half_applied`.

## Resume logic

- Read `checkpoint.json` if present.
- Abort if `input_hash` differs from current CSV.
- Resume from `phase` + `last_row_id + 1`.

## Circuit breaker

- After each batch, evaluate failure rate.
- If threshold exceeded, abort with a critical log and persist checkpoint.

## Prohibitions

- No user identity updates (create/update identity).
- No manual steps; any missing API => `pending(out_of_scope)`.
