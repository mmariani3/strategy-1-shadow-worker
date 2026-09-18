# Hands-off infrastructure, Phase 1

This first package adds a **disabled-by-default discovery runner**, durable operational history,
and native-cell-safe Journal delivery/reconciliation. It does not qualify candidates, construct
setups, confirm triggers, submit orders or establish full-session opportunity coverage.
Strategy Rules v0.3 and Experiment Plan v0.5 are unchanged. Existing discovery cron jobs are unchanged.

## Discovery plan and activation boundary

`shadow_operations.py --plan path.json` is an offline configuration preview. No database or network
connection occurs. Plans are explicit arrays of jobs, with exactly these fields:

```json
[
  {
    "session_date": "2026-09-18",
    "phase": "PREMARKET",
    "ruleset_version": "v0.3",
    "run_class": "INFRASTRUCTURE_TEST",
    "scheduled_at": "2026-09-18T06:00:00-07:00",
    "deadline": "2026-09-18T06:01:00-07:00",
    "movers_top": 20,
    "news_hours": 18
  }
]
```

This dated example is a local fixture, not a production schedule or permission to run it.
Each operational window must be declared before activation; it is not a new strategy threshold.
The stable key is the existing coordinator's strategy/date/phase/ruleset/class key. Duplicate jobs,
missing timezone/classification and edits to an already-persisted plan are refused.

After isolated acceptance and a separately reviewed deployment configuration:

- Apply `supabase/migrations/20260918173946_shadow_operation_events.sql`. This PR does not apply it remotely.
- `OPERATIONS_DATABASE_URL`: verified TLS, direct or **session-pooled** connection; transaction pooling cannot retain the advisory lock. The role must read discovery runs/items and append/read operation events. No broker credentials beyond the existing calendar GET authentication are used by the runner.
- `DISCOVERY_URL`: exact HTTPS service origin; `DISCOVERY_SCHEDULER_TOKEN`: scheduler-only credential.
- `ALPACA_API_KEY` / `ALPACA_API_SECRET`: existing authorized paper endpoint credentials for the **read-only calendar**.
- Both `SHADOW_OPERATIONS_ENABLED=true` and `--apply` are required to persist job history/dispatch.
- A hosted scheduler would invoke the reviewed plan repeatedly within its declared windows and after them for reconciliation. Its cadence, cost, hosting configuration and deployment have **not** been created or verified here. Do not concurrently enable the old cron path as an independent dispatcher.
- `--report` reads persisted events without dispatching; `--apply` also prints the resulting report. Output is JSON, not an installed notification service. Consumer-facing daily delivery and notification deduplication still need a configured transport. Repeated unchanged incidents do not create repeated history events.

The runner reads Alpaca's session calendar, including early closes, and checks the premarket/post-open
window against those hours. Unavailable/malformed calendar fails closed. A cold start that consumes
the window is MISSED; there is no late catch-up or backdating. Calendar closure differs from failure.

Before the only discovery POST, the runner holds a session lock and commits DISPATCHED intent.
A unique partial index forbids a second intent for that job. A timeout, process crash or uncertain
response is **not** automatically retried, including a crash between committing intent and sending.
Subsequent passes look up the existing source run and verify its identity, final state and item count.
IN_PROGRESS/incomplete evidence remains AMBIGUOUS. Operator reconciliation is needed if no source
run can establish the result. Terminal source outcomes preserve COMPLETE/PARTIAL/DATA_UNAVAILABLE.

The operation ledger is append-only for the backend role, with RLS and explicit revocation of broad
default grants. Its rows are infrastructure/process history, not trade observations. Original events
remain even after later successful reconciliation. Schema tests include the broad-default-grant case.

## Journal native structure and restart recovery

The writer still reads current Sheet values, reconciles stable IDs and holds its existing session lock.
Before writing it also reads bounded native cells and validates dropdowns. Formulas, rich-text/chip
cells, preexisting links, and structured/protected sheets fail closed for explicit review. Native
support is intentionally conservative; it does not extend tables or overwrite formulas.

Each immutable delivery patch now includes a versioned native before/after snapshot and sheet ID.
No Journal schema migration is required; these are additional keys inside the existing JSON patches.
Old ledger rows are preserved and are not silently upgraded.

One atomic Sheets `batchUpdate` sets explicit literal values and restores the original number format
and link field. This prevents date-format loss and auto-linking dotted ticker symbols. Text beginning
with `=` stays literal text. Readback must match both values and native metadata before VERIFIED.
Unrelated cell fields are outside the write mask. ISO dates remain text; no historical date conversion
or strategy/qualification field backfill is performed.

If a native delivery acknowledgement is lost:

```text
python journal_writer.py --reconcile-pending --apply
```

This requires the existing `JOURNAL_WRITES_ENABLED=true`, writer database/Sheet configuration and
Google credentials. It holds the same session lock, reads the stored patches and source snapshot,
and marks VERIFIED only if exact native/value readback and stable-ID reconciliation both pass.
It makes **zero Sheet writes**. Legacy patches, partial writes, user-edited results and mismatches stay
blocked for explicit reconciliation. A pending delivery is never deleted or cleared blindly.

Google Sheets provides no compare-and-swap guard against an unrelated human or third-party writer
editing between the final read and the write. The advisory lock protects cooperating writers only.
Retain the single approved writer and restrict competing edits during operation; reads/readback
detect many conflicts but are not a cross-system transaction.

## Validation performed for this change

- 116 Python tests, external HTTP blocked: original Worker/discovery/lifecycle/execution regressions,
  native cells, lost acknowledgements, default-disabled runner, windows/DST/early closes, calendar
  failure, stale plan refusal and source reconciliation.
- Four isolated PGlite migration suites: original schema/history preservation, default grants,
  append-only operation history and one dispatch intent per job.
- `tests/native_operations_acceptance.py`: loopback PostgreSQL, independent competing connection,
  durable intent visible before request, fresh-session recovery, one simulated request, no external HTTP.
- `tests/credentialed_writer_acceptance.py`: fresh loopback database and the existing workbook explicitly
  titled `INFRASTRUCTURE TEST - ...`; actual Google credential transport, date/ticker native readback,
  competing OS process, retry NOOP, ambiguous successful write and zero-write reconciliation.
- `tests/sheet_acceptance_probe.py` fixture now supplies the timestamp required since PR #3.

Run offline checks with the pinned Python development dependencies and `python -m pytest -q`;
run database checks with `npm run test:migration`. Native integration scripts require explicit
loopback connection files; the Google test additionally requires test credentials, a test-copy ID and
`--apply-test-writes`. Production Journal ID is refused, as are non-test workbook titles. Synthetic
fixtures exist only in isolated infrastructure environments and are excluded from Strategy #1 evidence.

## Remaining work before hands-off opportunity assessment

1. Approved evidence/review producer and independent SHADOW comparison. These are absent; the report
   deliberately returns opportunity outcome UNKNOWN even when discovery is complete.
2. Justified current-review validity, reliable required data/entitlements and supported qualitative
   judgments. Do not auto-fill booleans or invent numerical policy thresholds.
3. Hosted Google identity, secret renewal, database access, costs, run cadence, incident transport,
   session summaries and end-to-end deployed acceptance. Desktop OAuth is not proof of hosted readiness.
4. Prospective assessment dates/window only after those dependencies are verified. Nothing in this
   PR starts the ten-session block or enables paper/live execution.

No production services, database, Journal, schedules, living masters or synced reference files were
modified by this implementation/test package. Production activation is a separate reviewed step.

## API references checked

- [Google Sheets native cell fields](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/cells)
- [Google Sheets update requests](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/request)
- [Alpaca session calendar](https://docs.alpaca.markets/us/v1.1/reference/getcalendar-1)
- [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Supabase API exposure change](https://supabase.com/changelog/45329-breaking-change-tables-not-exposed-to-data-and-graphql-api-automatically)

The migration uses direct PostgreSQL access and makes no anonymous/authenticated Data API grants.
