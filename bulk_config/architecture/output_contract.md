# Output Contract

This file specifies the mandatory artifacts produced by the pipeline. All outputs must be **append-safe** and **flush on every row**.

## 1. rejected_rows.csv (pre-API failures)

- **Purpose**: Store rows rejected during schema/validation.
- **Append-safe**: Yes (append + flush per record).
- **Columns (minimum)**:
  - `timestamp`
  - `row_id`
  - `entity_type`
  - `entity_key`
  - `reason_code`
  - `reason_message`
  - `raw_row_minified`

## 2. results.csv (final status per input row)

- **Purpose**: The final outcome for each processed row in its phase.
- **Append-safe**: Yes (append + flush per record).
- **Columns (minimum)**:
  - `timestamp`
  - `batch_id`
  - `row_id`
  - `phase`
  - `entity_type`
  - `entity_key`
  - `step`
  - `status` (`success` | `pending`)
  - `http_status`
  - `message`
  - `remote_id`

## 3. pending_rows.csv (runtime failures or out-of-scope)

- **Purpose**: Rows that fail during execution or cannot be automated.
- **Append-safe**: Yes (append + flush per record).
- **Columns (minimum)**:
  - `timestamp`
  - `batch_id`
  - `row_id`
  - `phase`
  - `entity_type`
  - `entity_key`
  - `step`
  - `reason_code`
  - `reason_message`
  - `http_status`
  - `raw_row_minified`

## 4. checkpoint.json (resume state)

- **Purpose**: Safe restart from the last completed row per phase.
- **Write style**: Atomic (write temp + rename).
- **Schema**:
  - `pipeline_version` (int)
  - `input_hash` (sha256 of the full CSV content)
  - `phase` (1, 2, or 3)
  - `last_row_id` (int, last fully recorded row)
  - `started_at` (timestamp)
  - `updated_at` (timestamp)

## 5. Corruption policy

If any output file is detected as corrupt:
- Abort the run with a critical log.
- Do **not** continue without manual intervention.
