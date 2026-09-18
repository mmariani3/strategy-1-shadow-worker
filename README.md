# Strategy #1 Shadow Worker

See [audit remediation and acceptance guide](AUDIT_REMEDIATION.md) for the current input contract, migration, regression checks, journal writer, and rollout limitations.

See [research evidence packets and session reports](README-evidence-review.md) for the read-only review pipeline and its remaining acceptance requirements.

See [the opt-in automated research reviewer](README-automated-reviewer.md) for full-master model requests, durable attempt protection and reference comparison. Its outputs remain research-only.

Phase 1 shadow-mode worker for Strategy #1 v0.3.

It accepts structured candidate inputs, returns `TRADE`, `WAIT`, or `NO_TRADE`, and writes every decision to Supabase `public.strategy_signals`.

It **does not call Alpaca or the Paper Executor**.

## Render secrets

Set these only in Render environment variables:

- `SUPABASE_SECRET_KEY` — server-only Supabase secret key (`sb_secret_...` preferred).
- `WORKER_TOKEN` — generated bearer token protecting `/evaluate`.

Other config is included in `render.yaml`.

## Endpoints

- `GET /health`
- `POST /evaluate` with `Authorization: Bearer <WORKER_TOKEN>`

## Important guardrails

- Strategy #1 only.
- Ruleset v0.3 only.
- Tier C/no catalyst => `NO_TRADE`.
- Planned R/R < 1.5R => `NO_TRADE`.
- 1.5R–2.0R requires explicit `clean_structure`; it is not inferred.
- Missing qualitative inputs fail closed as `WAIT`.
- Daily risk/trade/notional ceilings are enforced.
- No broker execution exists in this service.
