# PR #1 isolated acceptance — September 15, 2026 PT

## Result

**Keep the PR in draft; do not merge yet.** Local, connector-assisted, and credentialed standalone writer checks passed. Full staging service integration remains unverified. No production code, schema, Journal record, or execution setting was changed.

## Review and fixes

The living masters were reread: Strategy Rules v0.3, Experiment Plan v0.5, Automation Specification v0.4. Target validation, explicit qualitative review, prospective confirmation, retained process evidence, legacy Signal Queue treatment, and the SHADOW boundary remain consistent with their governing requirements. No strategy or experimental-methodology threshold was added.

1. **Discovery state constraint:** read-only live catalog inspection found `strategy_discovery_items_operational_state_check` allowed only WATCHLIST_CANDIDATE and WORKER_READY. The first PR migration alone did not widen it. HOLD, rejection, and routed Worker-state writes would fail. `20260916001258_discovery_state_acceptance_fix.sql` now permits the states actually emitted, while retaining the original states and all historical values. A regression reproduces the original rejection before applying the migration chain and then verifies each new state.
2. **Journal dropdown compatibility:** the actual Scan Coverage cells allow Checked/Unavailable. The projection emitted internal CHECKED_ALPACA_NEWS and similar codes. It now maps recognized completed source checks to Checked and unresolved/unavailable/unknown states to Unavailable. Raw channel evidence stays in the delivery trace/database. Scan Status remains Partial when applicable; source checks do not imply full scan completion.

## Evidence

| Check | Result and scope |
| --- | --- |
| Python regression suite | 64 passed. Network blocked for unit tests. |
| Minimal migration suite | Passed historical preservation, audit rollback, role restrictions, one-pending-delivery constraint. |
| Live-schema reconstruction | Passed in isolated PGlite using captured table column types/defaults/nullability, constraints, indexes and update-trigger behavior. Reproduced and corrected the discovery-state error; retained original row fields; duplicate run still rejected. |
| Test Journal write/readback | 48 generated cell patches, 4 unique records: one Scan Coverage and three pre-signal candidate states. Fresh readback matched; a second reconciliation produced NOOP. |
| Strategy Journal | Read-only metadata/header/validation inspection; no writes. |
| Production Supabase | Read-only project, branch and schema inspection; no test rows or migrations applied. |
| Render deployment metadata | Four web services report live audited commit `edc71cd162078b165f13aaf34262ba6b377520b7`. All six services from this repository auto-deploy on commits to main. Web-service PR previews are off. |
| Runtime health/settings | After initial cold-start timeouts, all four public health endpoints returned ok, SHADOW, v0.3 and broker_execution_enabled=false. Orchestrator also reports trigger_confirmation_automatic=false. Actual risk environment values remain unverified. |

The [test workbook](https://docs.google.com/spreadsheets/d/1r_qpnfYin7mwNoO5__yAH_SA6wM0Y06wW42D43x6ImU/edit) is explicitly titled INFRASTRUCTURE TEST and is a separate copy. Its two process tabs contain only test rows with exclusion notes. Other copied tabs retain their copied contents and are not new evidence. No test record belongs in Strategy #1 validation metrics.

The earlier Sheet probe uses Google Drive connector transport. The subsequent `tests/credentialed_writer_acceptance.py` test exercises the actual standalone CLI with Google Application Default Credentials and native PostgreSQL 17.6 on loopback. It reconstructs the captured schema, applies both migrations, reads four source records, writes through Google Sheets API, verifies readback, and confirms a NOOP retry with exactly one row per stable ID. A second OS process is rejected while the first connection holds the session lock. A real Google write followed by an injected lost acknowledgement leaves a durable PENDING delivery; a fresh CLI process refuses to retry, while an independent Google read confirms the accepted write. The isolated ledger retains one VERIFIED and one PENDING record; no automatic recovery or clearing was performed.

All new Sheet records carry explicit INFRASTRUCTURE_TEST exclusion notes. The local database uses STRATEGY_1 branch fixtures solely to exercise the production projection guards; they never enter production or strategy evidence. This tests native PostgreSQL, not the hosted Supabase gateway/RLS configuration. The successful path invokes the unmodified standalone CLI; the lost-acknowledgement path injects a transport failure around the real Google write.

`tests/live_schema_snapshot.json` contains schema metadata only, no production row data or secrets. It is an isolated test fixture, not a deployment bootstrap or an export of all live grants, RLS policies, extensions, or numeric typmods. The companion test reconstructs the two timestamp-update functions' inspected behavior. PGlite is not the live Supabase runtime.

## Reproduction

```text
python -m pytest -q
npm run test:migration
python tests/sheet_acceptance_probe.py before.json after.json
python tests/credentialed_writer_acceptance.py --connection-file LOCAL_CONNECTION_JSON --credentials LOCAL_ADC_JSON --test-sheet DEDICATED_TEST_SHEET_ID --apply-test-writes
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
- [ ] Exercise authenticated Discovery → Orchestrator → Worker requests against isolated deployed services and the target migration chain.
- [x] Verify current health reports SHADOW, execution disabled, and automatic trigger confirmation disabled.
- [ ] Verify actual risk environment settings; health/metadata does not expose those values.
- [ ] Obtain separate production rollout authorization. Coordinate all six auto-deploying services and pause automatic deployment before merging if migration/service ordering requires it.
- [ ] Apply both migrations in order, verify new constraints/audit behavior, deploy compatible service/caller contracts, and confirm SHADOW with broker execution disabled before resuming scheduled work.
- [ ] Enable/schedule the journal writer only after independent acceptance; reconcile any ambiguous historical IDs explicitly. Never delete/relabel old test evidence as part of rollout.

The remaining staging integration and runtime-configuration checks are required before approving production activation. A merge today would trigger deployment, so it is not an administrative-only step.
