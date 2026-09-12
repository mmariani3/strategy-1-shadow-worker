# Strategy #1 Discovery Coordinator

Phase-1 shadow discovery service for Strategy #1.

What it automates:
- Alpaca top-mover/activity discovery.
- Alpaca news collection.
- Recent SEC EDGAR filing evidence for discovered U.S. symbols.
- Supabase discovery-run and candidate-funnel records.
- Scan Coverage status.
- Structured promotion into the existing Shadow Orchestrator after explicit review.

What it does NOT automate:
- Catalyst materiality judgment.
- Catalyst Tier A/B assignment.
- Cross-source verification judgment.
- Macro/economic calendar coverage (v0.1 marks this Data Unavailable / not integrated).
- Trade qualification or broker execution.

This is deliberate. Strategy #1 v0.3 requires broad discovery, cross-source verification, and explicit fail-closed handling of unresolved qualitative rules.

Required environment variables:
- RULESET_VERSION=v0.3
- DISCOVERY_SERVICE_TOKEN
- SUPABASE_URL
- SUPABASE_SECRET_KEY
- ALPACA_API_KEY
- ALPACA_API_SECRET
- ORCHESTRATOR_URL=https://strategy-1-shadow-orchestrator.onrender.com
- ORCHESTRATOR_TOKEN
- SEC_USER_AGENT=<descriptive app/contact string>

Endpoints:
- GET /health
- POST /scan/run-once
- GET /runs/latest
- POST /items/{item_id}/promote

The service never calls the Paper Executor or Alpaca Trading API.
