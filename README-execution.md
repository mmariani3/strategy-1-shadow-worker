# Strategy #1 Shadow Execution Consumer + Lifecycle Monitor

Implements the downstream automation specified by Strategy #1 Automation Specification without changing strategy rules.

## Phase-1 safety
- Default `EXECUTION_ENABLED=false`.
- In shadow mode `/consume/run-once` records `WOULD_SUBMIT` only and never calls `/paper/bracket`.
- `/monitor/run-once` only polls already-submitted execution records; with Phase 1 data it is normally a no-op.
- Only `TRADE` signals under the configured ruleset are considered.
- Missing executable fields fail closed.
- Duplicate signal IDs are skipped once audited.

## Environment variables
- `EXECUTION_ENABLED=false`
- `RULESET_VERSION=v0.3`
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `EXECUTION_SERVICE_TOKEN`
- `EXECUTOR_URL=https://day-trading-paper-executor.onrender.com`
- `EXECUTOR_TOKEN` (only needed for controlled paper submission/monitoring)

Keep `EXECUTION_ENABLED=false` throughout Phase 1 shadow validation.
