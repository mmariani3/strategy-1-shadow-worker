# Normal Coordinator: read-only rehearsal review package

October 15 update: see [connector bridge review](CONNECTOR-BRIDGE-REVIEW-2026-10-15.md)
and the new `../tooling/coordinator-connector-local-result-2026-10-15.json`.
The missing staging audit table is installed; the authenticated database-only
bridge proof passed. This older package remains historical evidence and its
source manifest must not be used for the changed implementation. Hosted
application rehearsal and notification delivery remain unaccepted.

Prepared October 13, 2026 Pacific. LOCAL IMPLEMENTATION ONLY. NOT DEPLOYED,
NOT ARMED, NO DATE SELECTED. This package requests no immediate activation.

## Purpose and completed local work

Test authenticated dependencies and shutdown before allowing any normal Coordinator
collection. This is a no-scan infrastructure rehearsal, not the six-channel discovery
acceptance, a Strategy #1 observation, or acceptance of Phase 1.

The explicit `create_rehearsal_app` factory installs only the authenticated read-only
preflight. The scan factory remains absent, including after successful preflight.
The default exported app remains locked. Neither app exposes qualification,
promotion, monitoring, broker orders, Journal writes or arbitrary SQL.

`coordinator_runtime_preflight.py` checks the actual staging service/database,
v0.3, deployed commit, all pinned local source bytes, authorization date and a
maximum 15-minute manifest window. It serializes probes, bounds each response to
256 KiB, disables redirects and retries, and limits the sequence to 20 seconds.
Credential values and provider diagnostics never enter its response.

Four GETs establish narrowly scoped authentication: paper calendar (including the
requested normal session and previous session), SPY SIP quote, one dated SPY raw
daily bar for that previous session, and at most one staging discovery-run ID.
The dates come from the actual calendar and America/New_York timezone, including
DST. Missing data, pagination, a nonstandard session or stale/incorrect code fails
closed. Raw prices are neither returned as approved references nor substituted for
snapshot fields. These probes do not establish full-universe coverage or database
integrity; independent complete database snapshots serve that separate purpose.

`coordinator_rehearsal_binding.py` assembles the fixed Render adapter, GET-only
runtime client, database collector, authenticated host callbacks and owned watchdog
handle. It rejects the scan-capable runtime client. The engine has no scan method,
no acceptance POST, no automatic notification send, and no arming output. Rehearsal
markers are exclusive and keyed by date/service/scope; changing code cannot reset
the one-attempt guard. The CLI remains disabled without explicit host bindings.

The independently launched watchdog has a distinct rehearsal mode. It checks the
dated permit and every pinned local file before constructing the Render client.
It may suspend only staging Discovery; it cannot resume, read environments or place
orders. Parent success requires the owned child's identity-bound result AND fresh
Render suspension readback before the parent issues cleanup suspension itself.
An outside suspension alone is insufficient proof of watchdog success.

## Proposed smallest hosted scope

Only existing staging Discovery `srv-dal8abbl550s73cj3jm0`, workspace
`tea-daholiqfngtc73ddk480`, and staging database `cihwmameyylixouggwxk` may participate.
All other ten services, especially both production schedules, production Discovery
and the order-capable executor, remain suspended. All auto-deploy stays off.
No new resources, schema changes, paid upgrades or credential copying.

Exact proposed start command, for later separately authorized deployment:

```
uvicorn coordinator_acceptance_app:create_rehearsal_app --factory --host 0.0.0.0 --port $PORT
```

The deploy must publish the reviewed local file manifest and pin the resulting real
commit/deployment. Never substitute deploy-latest. The older October 13 commit and
deployment do not contain this implementation and cannot validate it. A deployment
can itself start a runtime: any future deployment operation needs its own independent
shutdown guard and suspended readback, not just a request to leave it suspended.

The future nonsecret manifest has exactly `scope`, `session_date`, `commit`,
`source_hash`, `not_before`, and `expires_at`. Its scope is
`NORMAL_COORDINATOR_NO_SCAN`. The server reads it only through the explicitly invoked
factory. No usable manifest has been installed; sample dates must never be promoted
from unit tests. Existing provider secrets stay in their authorized environment.

## Timing and operation

1. Before the selected T0, independently verify the real publication/deployment,
   file hashes, private evidence directory, dependency runtime, living masters,
   authorization and all eleven suspended/off. Restore only staging DB after that
   authorization and isolation check; wait for ACTIVE_HEALTHY. Restoration is outside
   this rehearsal engine and must have its own cleanup owner.
2. Start between T0 and strictly before T0+30 seconds. Obtain complete read-only
   database snapshots/catalog, absent exact test key, no unfinished runs, no active
   pg_cron or conflicting schedules/processes. Preserve all original rows and digests.
   No metadata/identity check may be replaced with a caller-supplied success flag.
3. The independent watchdog must be ready before staging resume. Stop preparation
   if fewer than 30 seconds remain before T0+3 minutes. Resume staging once and
   attempt one bounded read-only preflight. Any timeout fails closed without replay.
4. At T0+3 minutes, let the watchdog suspend staging. Preserve its actual result
   and obtain independent all-eleven-off readback. Parent intervention can restore
   safety but cannot count as successful independent-watchdog acceptance.
5. Before pausing DB, collect independent post-rehearsal rows/catalog and compare
   full digests with baseline. Every existing record must be unchanged, with zero
   new run/item/event/protected-table records. Retain discrepancies; do not repair.
6. Pause staging DB only after all services are verified suspended/off, verify
   INACTIVE, refresh all-eleven-off again, then terminate only the owned watchdog
   handle if needed. Finish by T0+8 minutes. Authorization may last at most T0+15
   minutes, solely to permit bounded cleanup; it does not extend acceptance deadlines.

Early failure triggers suspension/readback and safe DB cleanup. If the attempt was
never acquired, the engine does not manipulate another owner's runtime; the operator
who restored the DB remains responsible for pausing it. Cleanup lateness and missing
readback remain failures. Never erase markers, resume for missing evidence, rerun a
timed-out attempt or roll the rehearsal to another date.

## Measurable acceptance

| Gate | Required proof | Current status |
| --- | --- | --- |
| Exact code/scope | Approved commit/deployment plus actual source-byte manifest and fixed rehearsal entry point | PASS offline; hosted NOT VERIFIED |
| Authentication | Four bounded authenticated GETs with valid response/date shapes; fixed status-only response | PASS offline; hosted NOT VERIFIED |
| No scan/write capability | GET-only desktop client, scan factory absent, zero acceptance POSTs and unchanged DB digests | PASS offline; hosted NOT VERIFIED |
| Isolation | Exact eleven-service inventory, correct owner, auto-deploy off, only staging temporarily active | PASS offline; current hosted state NOT VERIFIED |
| Watchdog | Owned process/program/nonce/permit receipt before resume; child suspension result plus provider readback | Separate process proven offline; real rehearsal mode/Render action NOT VERIFIED |
| Database preservation | Complete baseline/readback, same schema hash, all old rows unchanged and no added records | PASS with fake DB; PostgreSQL/roles/RLS/concurrency NOT VERIFIED |
| Cleanup | All eleven suspended/off, staging DB INACTIVE, owned child exited by T0+8 minutes | PASS offline; hosted NOT VERIFIED |
| Notifications | Recipient-confirmed missing/stalled/first/second consecutive/cleanup-failure cases | NOT VERIFIED; this rehearsal sends no messages |
| Full normal discovery | Six-channel sufficiency, actual catalyst/issuer/event review and traceable REVIEW_REQUIRED persistence | NOT VERIFIED; outside this rehearsal |

Fail any required row and the corresponding gate stays unaccepted. A successful
no-scan rehearsal does not validate storage mutations, duplicate races, complete
discovery, eligible decisions, executions, monitoring or Journal reconciliation.
No automated Strategy #1 validation sample is created.

## Concrete unresolved connections and approval decisions

- The desktop database collector needs an authenticated, fixed-staging connection
  with complete visibility and an approved runtime driver, or a separately reviewed
  connector bridge with equivalent complete-snapshot guarantees. A project-ID string
  or successful one-row REST read is insufficient. No new database password was
  requested, loaded or assumed available. Prefer the existing authenticated Supabase
  connector if a complete readback bridge can meet the consistency/time requirements.
- Live master, caller, project-status and pause callbacks must use authenticated
  host integrations. Unit-test callbacks are not such integrations. Local process
  inventory was permission-denied in the preceding slice; that remains unresolved.
- Private evidence storage/ACLs, actual runtime dependencies and deployment shutdown
  need review. Stored permit IDs or hashes alone do not prove user authorization.
- Notification delivery acceptance is separate. No unattended discovery run may be
  armed until required notification cases and cleanup safeguards are independently
  proven. This rehearsal has no email sender. A supervised no-scan rehearsal requires
  a specifically available cleanup operator; it is not an assumption about Mitch's
  availability. Desktop/network failure can defeat both local processes.
- Publication to the existing repository/staging service, bounded credential reuse,
  installing the nonsecret manifest and one selected rehearsal window each require
  explicit scope. The expired October 13 permission has not been extended. Approval
  of local implementation is not approval for those external actions.

Next authorization: review this exact local patch for publication/staging deployment
preparation, with no scan or schedule activation. A live rehearsal must wait until
the connections above are demonstrated and its date, cleanup owner and bounded
credential-use window are recorded. There is no ready-to-arm unattended package yet.

## Evidence and governing sources

Current result, exact changed-file hashes and cumulative patch:
`../tooling/coordinator-preflight-local-result-2026-10-13.json`.
Prior adapter/controller results and original October 13 acceptance records are
preserved. All fifteen originally pinned October 13 files must still match.

Rules v0.3, Experiment Plan v0.5 and Automation Specification v0.4 retain their
separate authority. This slice changes infrastructure only; it does not change
strategy rules, validation criteria or eligibility. Latest saved live-master
revision evidence is `../tooling/coordinator-launch-authorities-2026-10-13.json`;
masters were not refreshed again in this local-only slice and must be refreshed
before future launch. Production schedules and ChatGPT weekday oversight should
remain paused. Their current hosted state was not queried here.

Interface references: [Alpaca historical bars](https://docs.alpaca.markets/us/reference/stockbars),
[Alpaca calendar](https://docs.alpaca.markets/us/v1.4.2/reference/getcalendar-1),
[Supabase REST API](https://supabase.com/docs/guides/api),
[Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys).
Public documentation was consulted; authenticated provider endpoints were not called.
