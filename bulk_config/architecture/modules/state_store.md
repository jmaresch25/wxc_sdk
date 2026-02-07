# Module: state_store.py

## Purpose
Manage checkpoint read/write with atomicity and corruption handling.

## Required behaviors

- Write checkpoint as temp file + rename (atomic).
- Ensure checkpoint is only advanced after outputs are persisted.
- Read checkpoint defensively:
  - If JSON parse fails => abort with critical error.
  - If schema missing required fields => abort.

## Checkpoint schema

See `output_contract.md` for the definitive fields.
