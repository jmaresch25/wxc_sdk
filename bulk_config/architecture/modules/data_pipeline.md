# Module: data_pipeline.py

## Purpose
Validate, normalize, and deduplicate the single input CSV; emit `ready_to_load.csv` and `rejected_rows.csv`.

## Required behaviors

1. **Validation (pre-API)**
   - Enforce the input schema in `input_schema.md`.
   - Reject out-of-scope user identity fields.
   - Validate data types and formats (email, extension, phone number).
   - Enforce uniqueness rules (location_key, extension per location, user email as required).

2. **Normalization**
   - Normalize casing and whitespace.
   - Derive `entity_key` when missing (see input schema rules).
   - Normalize booleans (e.g., `calling_enabled` defaults to true).

3. **Deduplication**
   - Detect duplicate keys for uniqueness constraints.
   - Emit `rejected_rows.csv` with `reason_code=duplicate_key`.

4. **Output**
   - `ready_to_load.csv` with normalized fields (same column schema as input plus derived `entity_key` and `row_id`).
   - `rejected_rows.csv` for pre-API failures only.
   - Append-safe writing with flush per row.

## Rejection rules

- Any schema violation => `invalid_input_schema`.
- Duplicate keys => `duplicate_key`.
- Presence of identity attributes in user rows => `out_of_scope`.
