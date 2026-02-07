# Module: writers.py

## Purpose
Write append-safe CSV outputs and ensure flush per row.

## Required behaviors

- Append-safe writing for `results.csv`, `pending_rows.csv`, `rejected_rows.csv`.
- Flush after every row to protect against crashes.
- Serialize `raw_row_minified` as compact JSON of relevant columns.
- Detect output corruption and abort with critical error.

## Output columns

See `output_contract.md` for required columns.
