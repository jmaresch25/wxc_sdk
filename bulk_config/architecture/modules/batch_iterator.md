# Module: batch_iterator.py

## Purpose
Stream `ready_to_load.csv` by phase and `entity_type`, emitting deterministic batches.

## Required behaviors

- Process rows in fixed phase order (see runtime guarantees).
- Within each phase, process only the `entity_type` values assigned to that phase.
- Enforce limits: `MAX_ROWS`, `BATCH_SIZE`, `MAX_BATCHES`.
- Provide deterministic `batch_id`: `<phase>-<sequential_batch_number>`.
- Support resume by skipping rows <= `checkpoint.last_row_id` for the active phase.

## Output

- A generator/iterator interface that yields batches with:
  - `batch_id`
  - `phase`
  - `rows` (list of row objects)
  - `row_id` for each row

## Failure modes

- If limits are exceeded, exit cleanly and allow checkpoint persistence.
- If `ready_to_load.csv` is missing or malformed, abort with a critical error.
