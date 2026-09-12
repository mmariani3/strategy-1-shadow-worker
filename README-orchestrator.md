# Strategy #1 Shadow Orchestrator

Phase-1-only candidate ingestion and prospective trigger-observation service.

## Safety boundary

- Never submits broker orders.
- Never calls the Paper Executor.
- A price crossing a predefined level is recorded as `TRIGGER_OBSERVED`, **not** as Strategy #1 trigger confirmation.
- Qualitative confirmation remains an explicit structured input until the living Strategy Rules/Automation Specification operationalize it.
- Fails closed when consolidated data is required but the configured feed is not SIP.

## Endpoints

- `GET /health`
- `POST /candidates/ingest`
- `GET /candidates/active`
- `POST /monitor/run-once`
- `POST /candidates/{candidate_id}/confirm-trigger`

## Required environment variables

- `RULESET_VERSION=v0.3`
- `ORCHESTRATOR_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `STRATEGY_WORKER_URL=https://strategy-1-shadow-worker.onrender.com`
- `WORKER_TOKEN`
- `ALPACA_API_KEY`
- `ALPACA_API_SECRET`
- `ALPACA_DATA_FEED=iex` (or `sip` only if actually entitled)

Do not paste secrets into chat. Add them directly in Render.
