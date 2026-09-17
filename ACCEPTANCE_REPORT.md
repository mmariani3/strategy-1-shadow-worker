# PR #1 isolated acceptance — September 15, 2026 PT

## Result

**Keep the PR in draft pending production rollout authorization.** Local HTTP service integration, credentialed standalone writer checks, read-only configured risk-limit verification, and bounded hosted staging acceptance passed. Hosted acceptance verifies real transport, RLS, traceability, and infrastructure exclusion; it does not establish real-market prospective behavior or a hosted journal-writer deployment. No production code, schema, Journal record, or execution setting was changed.

## Review and fixes

The living masters were reread: Strategy Rules v0.3, Experiment Plan v0.5, Automation Specification v0.4. Target validation, explicit qualitative review, prospective confirmation, retained process evidence, legacy Signal Queue treatment, and the SHADOW boundary remain consistent with their governing requirements. No strategy or experimental-methodology threshold was added.

1. **Discovery state constraint:** read-only live catalog inspection found `strategy_discovery_items_operational_state_check` allowed only WATCHLIST_CANDIDATE and WORKER_READY. The first PR migration alone did not widen it. HOLD, rejection, and routed Worker-state writes would fail. `20260916001258_discovery_state_acceptance_fix.sql` now permits the states actually emitted, while retaining the original states and all historical values. A regression reproduces the original rejection before applying the migration chain and then verifies each new state.
2. **Journal dropdown compatibility:** the actual Scan Coverage cells allow Checked/Unavailable. The projection emitted internal CHECKED_ALPACA_NEWS and similar codes. It now maps recognized completed source checks to Checked and unresolved/unavailable/unknown states to Unavailable. Raw channel evidence stays in the delivery trace/database. Scan Status remains Partial when applicable; source checks do not imply full scan completion.
3. **Confirmation transport failure:** real HTTP integration found `context_updates` replaced JSON-encoded daily-loss values with Python Decimal objects. A confirmation/resume request then failed with HTTP 500 before its database PATCH. The method now retains Pydantic's JSON encoding while explicitly clearing omitted assessments. A focused JSON serialization regression and the full HTTP lifecycle pass.

## Evidence

### Hosted staging — September 16, 2026

Three separate Free Render services (Worker, Orchestrator, Discovery) deployed commit `242e33c8fd4aad68f039baeecf9afbc55bfe4843`, with automatic deployment off. Supabase project `cihwmameyylixouggwxk` is a separate $0/month staging project with a schema-only baseline and both PR migrations; no production rows were copied. The attempted database branch was refused because it required Pro; no upgrade or paid branch was created.

The first hosted attempt exposed a compatibility defect: a legacy service-role JWT sent only as `apikey` returned no rows under RLS, so Discovery reported an existing test item missing. The three components now also send a bearer header for JWT-shaped server keys; modern secret-key behavior is unchanged. `tests/test_database_auth.py` covers both formats. The legacy format was verified against hosted Supabase; the modern format was regression-tested locally. The first failed attempt's infrastructure discovery records are preserved.

`tests/hosted_staging_acceptance.py` passed actual Render → Supabase and Discovery → Orchestrator → Worker checks: three SHADOW health endpoints, disabled execution, unauthenticated rejection, publishable-role read/write denial, separate qualification, structured setup handoff, idempotent replay, applicable trace IDs, actual Worker commit/fingerprint, and retained infrastructure classification. Both infrastructure fixtures correctly produce REJECTED/NO_TRADE with reason INFRASTRUCTURE_TEST, never a strategy WAIT or TRADE, and never enter market monitoring. Discovery's intermediate readiness is checked separately in immutable history: missing quality holds; complete structured setup reaches WORKER_READY before the Worker rejects its infrastructure class.

Successful test identities:

| Run | Candidate / discovery item | Signal |
| --- | --- | --- |
| `3f377d7c-769f-48e5-bec2-9102487aab5d` | `97176458-9708-4a84-a95a-150700485123` | `5e74ac59-27f6-41c5-a235-addd4b97cefa` |
| `c55a1406-a8b5-4f04-95d9-cd8dd4e9e3e9` | `c942d732-7259-4299-9b92-55ed7f4bba4b` | `30c85d6b-6774-49f7-b974-c47520baa268` |
| `ab31c049-296f-44c1-8116-5abf058ffb2e` | `34011b82-25bd-45e2-ad90-29ab0c1c91be` | `572ade0d-bf1f-4fec-956f-63ff94beedd7` |
| `16243c11-2d37-4f27-8d3b-b0531d15b0e5` | `9888b315-c6d4-46fd-bdf0-6f9f6c7a90b7` | `4250fefa-c74d-475c-86b1-e1bf1130893a` |

All journal IDs follow `S1-20260916-INFRA-<candidate UUID>` and match across candidate/signal records. The final two rows are the expanded acceptance rerun. No Sheet writes occurred during hosted acceptance. No broker credentials, market-data credentials, schedules, execution consumer, or journal writer were provisioned in staging. Orchestrator's IEX default is not evidence of consolidated data availability. Fresh staging error-log inspection returned no error entries.

Supplemental read-only history checks verified one signal per candidate, intermediate readiness states, and database-trigger transitions with timestamps, owner, reason, and implementation version. A direct catalog check confirmed that both anon and authenticated lack SELECT on private audit/ledger tables. Follow-up probes encountered intermittent TLS timeouts/resets; after those transient failures, the expanded full acceptance rerun passed all eleven checks, including populated-table RLS and HTTP denial of private audit/ledger reads. Earlier failed attempts remain documented and their records preserved; continuous availability is not established by a passing test.

The original audit's full lifecycle cases remain established by the isolated quote-injected integration and regression tests, not by these hosted synthetic records. Production loaded-process risk configuration and real-market prospective eligibility remain unverified. The active cleanup reminder reviews staging every 12 hours, with target review by September 16, 10:24 PM Pacific; it is a reminder, not automatic cancellation.

### Earlier isolated and read-only evidence

| Check | Result and scope |
| --- | --- |
| Python regression suite | 67 passed, including both database credential formats. Network blocked for unit tests. |
| Local service integration | Real authenticated HTTP between Discovery, Orchestrator and Worker, PostgREST 16.3, native PostgreSQL 17.6. Twelve acceptance checks passed; only the quote provider and Supabase key gateway are test adapters. |
| Configured Worker risk limits | Read-only Render environment inspection: MAX_DOLLAR_RISK=50, MAX_DAILY_LOSS_DOLLARS=100, MAX_TRADES_PER_DAY=3, MAX_NOTIONAL=10000. These match the governing rules. No environment edit or deploy occurred; loaded-process values are not independently exposed. |
| Minimal migration suite | Passed historical preservation, audit rollback, role restrictions, one-pending-delivery constraint. |
| Live-schema reconstruction | Passed in isolated PGlite using captured table column types/defaults/nullability, constraints, indexes and update-trigger behavior. Reproduced and corrected the discovery-state error; retained original row fields; duplicate run still rejected. |
| Test Journal write/readback | 48 generated cell patches, 4 unique records: one Scan Coverage and three pre-signal candidate states. Fresh readback matched; a second reconciliation produced NOOP. |
| Strategy Journal | Read-only metadata/header/validation inspection; no writes. |
| Production Supabase | Read-only project, branch and schema inspection; no test rows or migrations applied. |
| Render deployment metadata | Four web services report live audited commit `edc71cd162078b165f13aaf34262ba6b377520b7`. All six services from this repository auto-deploy on commits to main. Web-service PR previews are off. |
| Runtime health/settings | All four public health endpoints returned ok, SHADOW, v0.3 and broker_execution_enabled=false. Orchestrator also reports trigger_confirmation_automatic=false. Configured risk values are verified separately above; process introspection is not available. |

The [test workbook](https://docs.google.com/spreadsheets/d/1r_qpnfYin7mwNoO5__yAH_SA6wM0Y06wW42D43x6ImU/edit) is explicitly titled INFRASTRUCTURE TEST and is a separate copy. Its two process tabs contain only test rows with exclusion notes. Other copied tabs retain their copied contents and are not new evidence. No test record belongs in Strategy #1 validation metrics.

The earlier Sheet probe uses Google Drive connector transport. The subsequent `tests/credentialed_writer_acceptance.py` test exercises the actual standalone CLI with Google Application Default Credentials and native PostgreSQL 17.6 on loopback. It reconstructs the captured schema, applies both migrations, reads four source records, writes through Google Sheets API, verifies readback, and confirms a NOOP retry with exactly one row per stable ID. A second OS process is rejected while the first connection holds the session lock. A real Google write followed by an injected lost acknowledgement leaves a durable PENDING delivery; a fresh CLI process refuses to retry, while an independent Google read confirms the accepted write. The isolated ledger retains one VERIFIED and one PENDING record; no automatic recovery or clearing was performed.

All new Sheet records carry explicit INFRASTRUCTURE_TEST exclusion notes. The local database uses STRATEGY_1 branch fixtures solely to exercise the production projection guards; they never enter production or strategy evidence. This tests native PostgreSQL, not the hosted Supabase gateway/RLS configuration. The successful path invokes the unmodified standalone CLI; the lost-acknowledgement path injects a transport failure around the real Google write.

`tests/live_schema_snapshot.json` contains schema metadata only, no production row data or secrets. It is an isolated test fixture, not a deployment bootstrap or an export of all live grants, RLS policies, extensions, or numeric typmods. The companion test reconstructs the two timestamp-update functions' inspected behavior. PGlite is not the live Supabase runtime.

`tests/isolated_service_acceptance.py` copies the isolated writer-test database and starts three real service processes plus PostgREST. A local gateway checks a test API key and supplies a service-role JWT. The service launcher refuses non-loopback HTTP and replaces only the market quote provider with an explicit fixture. Verified: missing-auth rejection, qualification without constructing a candidate, incomplete setup HOLD, idempotent setup replay, monitoring excludes HOLD, crossing only observes, explicit resume retains prior observation events, unapproved target remains HOLD after confirmation, negative missed-trigger review produces NO_TRADE, clean prospective confirmation produces a SHADOW TRADE, all applicable trace IDs and implementation fingerprint persist, and infrastructure classification survives handoff. Fixtures are local-only and never strategy evidence; no market discovery scan or real broker/market API was called. The successful run database is `services_acceptance_8c3a5cbb06464a9ca72a6f1a3b5da4e4`. All temporary HTTP services stop after the test.

## Reproduction

```text
python -m pytest -q
npm run test:migration
python tests/sheet_acceptance_probe.py before.json after.json
python tests/credentialed_writer_acceptance.py --connection-file LOCAL_CONNECTION_JSON --credentials LOCAL_ADC_JSON --test-sheet DEDICATED_TEST_SHEET_ID --apply-test-writes
python tests/isolated_service_acceptance.py --connection-file LOCAL_CONNECTION_JSON --template-db WRITER_ACCEPTANCE_DATABASE --postgrest POSTGREST_EXECUTABLE --postgres-bin POSTGRES_BIN_DIRECTORY
python tests/hosted_staging_acceptance.py --connection-file IGNORED_STAGING_CONNECTION_JSON --expected-commit 242e33c8fd4aad68f039baeecf9afbc55bfe4843 --apply-staging-fixtures
```

For the Sheet probe, snapshots contain the complete bounded grids of a dedicated test workbook, keyed by Scan Coverage/Premarket Candidates, each with `values` and `row_count`. The first invocation without `after.json` produces the patches; the second validates fresh connector readback and asserts one matching stable-ID row and NOOP retry. Never apply its fixtures to the production Journal.

## Remaining acceptance and rollout checklist

- [x] Review against fresh living masters.
- [x] Inspect actual database constraints and Sheet validations.
- [x] Reproduce and fix both compatibility failures.
- [x] Verify isolated migration chain and connector-assisted Sheet reconciliation.
- [x] Verify Render auto-deploy behavior and deployed commit metadata.
- [x] Provision isolated native PostgreSQL and local Google credentials. Credentials stay in ignored local storage; the test rejects non-loopback databases, the production Sheet ID, and workbooks without an INFRASTRUCTURE TEST title. No remote development branch was created.
- [x] Run the standalone writer with real database source reads, competing processes, successful readback, durable ambiguous-write blocking, and NOOP retry. Explicit operator reconciliation after an ambiguous delivery remains a manual procedure; automatic recovery is intentionally absent.
- [x] Exercise authenticated Discovery → Orchestrator → Worker requests across isolated local processes, real PostgREST, and the target migration chain.
- [x] Verify bounded hosted staging transport, authentication/RLS, setup handoffs, traceability, retries, and infrastructure exclusion. Real-market lifecycle parity and hosted journal scheduling are not claimed.
- [x] Verify current health reports SHADOW, execution disabled, and automatic trigger confirmation disabled.
- [x] Verify configured risk environment settings through the Render dashboard (read-only); loaded-process introspection remains unavailable.
- [ ] Obtain separate production rollout authorization. Coordinate all six auto-deploying services and pause automatic deployment before merging if migration/service ordering requires it.
- [ ] Apply both migrations in order, verify new constraints/audit behavior, deploy compatible service/caller contracts, and confirm SHADOW with broker execution disabled before resuming scheduled work.
- [ ] Enable/schedule the journal writer only after independent acceptance; reconcile any ambiguous historical IDs explicitly. Never delete/relabel old test evidence as part of rollout.

Production runtime-configuration checks, migration/caller ordering, and separate approval remain required before production activation. A merge today would trigger deployment, so it is not an administrative-only step.
