# Local adapters and independent watchdog

October 13, 2026 Pacific. LOCAL ONLY / NOT ARMED / HOSTED APP LOCKED.

Subsequent local status: `REHEARSAL-REVIEW-PACKAGE.md` supersedes the missing
server-preflight implementation below. It adds a read-only factory and no-scan
rehearsal binding; actual authenticated host connections remain unconfigured.
The historical evidence for this adapter slice is preserved unchanged.

This slice implements fixed-endpoint clients, evidence collection and a separate
watchdog process. Tests use invented responses and credentials. No encrypted
credential store was opened; no hosted service, trading API or database was called.
No code was published, no hosted configuration changed and no date was selected.

## Implemented and tested locally

- `coordinator_service_adapters.py` restricts HTTP methods and destinations,
  disables redirects/retries and inherited session authentication, bounds response
  sizes/time, checks authorization expiry and redacts failures. Render suspension
  requires status readback. The watchdog client cannot resume or read environments.
- `DatabaseCollector` uses a dedicated psycopg-compatible connection with named
  cursors inside a repeatable-read, read-only transaction. It collects eight fixed
  tables, counts, row digests and schema/index/trigger/function/constraint evidence;
  bounds time/rows/bytes; checks callers and pg_cron; and rejects incomplete evidence
  or unconfirmed connection cleanup. No query has run against an actual database.
- `EvidenceCollector` hashes actual local files, preserves its initial snapshot,
  and rejects stale evidence instead of assigning old reads a current timestamp.
- `coordinator_driver.py` owns the actual child-process handle, validates the
  watchdog program hash, enforces clock coherence and only stops the child after
  verified service/database cleanup. Its CLI remains disabled. Credentials would
  travel through a private stdin pipe, never command-line arguments or diagnostics.
- `coordinator_watchdog_process.py` checks fixed scope, date, policy/source hashes
  and deadlines before its Render mode can run. It uses both wall and monotonic
  deadlines for suspension, bounded attempts and safe result records. It handles
  staging service suspension only; the controller remains responsible for pausing
  the database and checking all eleven services.
- Actual separate-process tests exercise explicit OFFLINE mode, modifying only a
  local fake-provider file. They cover delayed/failed suspension and survival after
  the launcher exits. They do not prove Render suspension or desktop outage safety.

Results, exact hashes, preserved test errors and cumulative diff are recorded in
`../tooling/coordinator-adapters-local-result-2026-10-13.json`.

## Remaining trust boundaries and blockers

1. The exported web app is locked and has no `/acceptance/preflight` route. The
   runtime client will fail closed until an authenticated read-only preflight and
   reviewed dated admission binding are implemented. Health is insufficient.
2. A database factory labelled with the staging project ID does not prove its
   actual destination. A reviewed launcher must bind authenticated connection
   identity, permissions and TLS to the existing staging project. No connection
   credential loader or live connector bridge is configured here.
3. Living-master, caller, project-status/pause, notification, rehearsal and arming
   callbacks require authenticated integration. Supplied JSON is not independent
   proof. No real notification delivery is claimed.
4. Render verifies deployment/commit and start command, but does not establish
   the source hash: the adapter returns the pinned policy hash. Publication proof
   and authenticated runtime hash evidence must independently establish the bytes.
5. Actual PostgreSQL role/RLS/schema behavior, concurrency, audit triggers, query
   budgets, network failures, runtime dependencies, private-directory permissions
   and hosted watchdog cleanup remain unverified. An OS-wide process inventory
   check was denied by local permissions; owned test-process handles are checked
   by the tests, but no system-wide shutdown claim is made.
6. The independent child shares desktop/network/provider risk with the controller.
   It is not an external recovery service. Unverified mandatory notification or
   cleanup safeguards block unattended admission.

Six-channel source sufficiency, semantic catalyst review and authenticated reviewer
ingestion retain their separate gates in `SOURCE-COVERAGE-CONTRACT.md`. Dated raw
closes remain separate, unapproved evidence. Infrastructure records never become
eligible strategy observations. Qualification, promotion, broker execution and
Journal delivery remain disabled in this acceptance path.

## Smallest next step

Implement and offline-test the server's authenticated read-only preflight and the
remaining reviewed launcher bindings. Then prepare an exact, bounded no-scan
rehearsal package with publication identity, protected evidence storage, delivery
checks, independent suspension and database cleanup. Seek hosted deployment,
bounded credential reuse and rehearsal authorization only for that concrete
package. No previous October 13 authorization or marker rolls forward.

Production schedules, executor and weekday oversight should remain paused. Their
current hosted state was not rechecked in this local-only slice. Phase 1 is not
accepted and Phase 2 is not ready.

Implementation references: [Render suspension API](https://api-docs.render.com/reference/suspend-service-1),
[Render service fields](https://api-docs.render.com/reference/service-fields),
[PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html),
[PostgreSQL read-only transactions](https://www.postgresql.org/docs/current/sql-set-transaction.html).
These specify interfaces, not observed hosted acceptance.
