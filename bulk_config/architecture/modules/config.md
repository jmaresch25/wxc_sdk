# Module: config.py

## Purpose
Define runtime configuration from environment variables with safe defaults and validation. No secrets are logged.

## Required settings

- `ENVIRONMENT` (lab|prod)
- `WEBEX_BASE_URL`
- `WEBEX_TOKEN`
- `OUTPUT_DIR`

## Defaults (provisional)

- `BATCH_SIZE=500`
- `MAX_ROWS=21000`
- `MAX_RETRIES=5`
- `REQUEST_TIMEOUT_SECONDS=20`
- `CONNECT_TIMEOUT_SECONDS=5`
- `CIRCUIT_BREAKER_THRESHOLD=0.80`
- `ENABLE_SAFE_COMPENSATION=false`
- `PIPELINE_VERSION=1`

## Validation rules

- Env values must be parsed and validated at startup.
- `ENVIRONMENT` must be one of `lab|prod`.
- Numerical values must be positive integers.
- Any invalid env var => abort with a clear error message.

## Security

- Never log token values or sensitive headers.
- Log only the presence of required variables.
