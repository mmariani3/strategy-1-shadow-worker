# Normal Coordinator staging acceptance — local implementation only

Prepared October 13, 2026 under authorization for local implementation and
offline tests. This is NOT a deployment, hosted acceptance, launch marker,
credential-use extension, scheduled run, Phase 1 acceptance or Phase 2 approval.

## Baseline and authority

The original `../discovery-prior-close-integration/` package and all October 13
evidence remain untouched. Baseline commit:
`46cec706384d68d0b3d29c5bf4210e38dfce4048`, deployment
`dep-db6qhj59fdbs73dv90v0`. October 13 accepted isolated collection/storage,
not the normal Coordinator. 13,228 coverage records included 13,213 available
dated raw closes and 15 explicitly unavailable closes. No snapshot repair was
accepted. Governing masters remain Rules v0.3, Experiment v0.5, Automation v0.4;
the live revisions were refreshed for the preceding plan on October 13.

## What changed locally

`coordinator_acceptance_app.py` calls the actual
`discovery_coordinator.run_scan` function. It does not implement a second scan.
The acceptance-specific Controls context bounds source and database access;
the ordinary, non-acceptance request path remains available in the source and
is NOT the approved future hosted entry point. Only the restricted app may be
considered for a later deployment. Its exported `app` is LOCKED: it has no
verified controls factory and cannot start a scan even with valid credentials.

The context verifies exact staging Discovery ID, exact staging Supabase URL,
v0.3, PREMARKET, INFRASTRUCTURE_TEST, dated-evidence inclusion, the supplied
session date and the 06:00:00–06:00:59 Pacific admission window before claiming
a run. No date is configured or armed in this package. Authentication is still
required. Additional routes, including rejection during the hosted acceptance,
qualification, setup, promotion, scheduled calls and Journal routes, are denied.
The underlying qualification/setup/persistence helpers also deny acceptance
context calls before their side effects. SHADOW and broker-disabled output is
explicit; there is no broker submission route or allowed order destination.

The normal collector retains its original source normalization and conservative
review semantics. The new path adds:

- Six distinct channel evidence records with source transport outcomes,
  category lead IDs, missing coverage and explicit incomplete status. Successful
  provider retrieval is not complete channel coverage. A zero-result response
  differs from unavailable retrieval. Symbol-less news is preserved for review.
- Explicit SEC lookup outcomes, declared filing window, timestamp and invalid
  response handling. Metadata retrieval does not establish document contents,
  freshness, materiality, same-event verification or source independence.
- Original snapshot fields preserved, plus separate dated evidence for every
  discovered symbol when the accepted collector has that symbol. News-only
  leads can receive dated evidence. Symbols outside that universe retain an
  explicit unavailable reason. Raw closes cannot become approved references.
- Run-key/symbol/source trace, unapproved event time, no inferred verification,
  no tier, no qualification, and REVIEW_REQUIRED items. Offline rejection
  fixtures test attributable REJECTED state without manufacturing hosted cases.
- Fixed-target storage; at most 20,000 leads; batches limited to 100 rows and
  1 MiB including audit context. Each batch is written once. Acknowledgements,
  full ordered paginated readback, and exact field digests must agree. Lost
  acknowledgement remains failure even if readback matches. Every mutation
  carries implementation identity and infrastructure-exclusion audit context.
- A unique run claim plus request/implementation fingerprint. Repeated requests
  return the existing result; changed request/code with the same key conflicts.
  IN_PROGRESS is never restarted. No upsert, blind replay or repair is added.
- Final run readback checks every submitted finalization field, not just count.

## Storage decision and limits

Use existing run notes/item JSON and existing audit triggers/indexes. No schema
migration is included. The run retains full universe/collection manifests and
distinct candidate-count semantics. Candidate rows contain discovery leads;
coverage-only rows are NOT expanded into candidates or separately persisted by
this Coordinator change. The October 13 universe ledger remains preserved.
This deliberately small scope is labelled `universe_coverage_rows_persisted=false`.
Any later requirement to store a new full-universe ledger alongside each normal
scan requires an explicit storage design; do not silently mix record kinds.

Source requests share an absolute 06:10 cutoff and a 2,000-request ceiling.
Accepted activity/prior collectors retain their own tighter budgets. Database
operations stop at 06:15. Socket timeouts are bounded and late responses rejected,
but these are NOT process-kill guarantees. An independent watchdog is required
before any future activation. SEC follow-up truncation is explicitly unavailable;
it cannot be represented as a complete source review.

## Offline verification and honest limits

`tests/test_coordinator_acceptance.py` exercises the normal scan function with
invented source responses and an in-memory PostgREST-like store. It covers source
failures, missing/incorrect scope/auth/date, independent channel reporting,
snapshot preservation, news-only prior attachment, symbol-less news retention,
blocked routes and direct helpers, duplicate/reconstructed controller requests,
unique-claim conflict, changed payload, lost acknowledgement, corrupted readback,
multi-page storage, prior-row preservation, deadlines and error redaction.

`coordinator_acceptance_verify.py` independently checks complete readback inputs:
prior-row equality, protected table state, exact new run/items, field digests,
all six channel records, prior-session/feed bindings, experiment exclusion and
item/run audit chains. Corrupted evidence fixtures must fail. Simulated triggers
and uniqueness conflicts do NOT prove PostgreSQL concurrency or actual triggers.
`coordinator-acceptance-readback.sql` is an unexecuted read-only template. Real
schema/index/trigger, pagination and audit acceptance remains a hosted gate.

The output is always PARTIAL/INFRASTRUCTURE_TEST with strategy eligibility false.
Storage success is reported separately. This package does not provide full
channel-specific source coverage, semantic catalyst approval, Journal delivery,
strategy observations, broker execution, monitoring or experiment acceptance.

## Remaining gates before any hosted authorization

1. Review the exact local diff and storage/source contracts. Confirm adequate
   coverage for earnings, corporate, analyst, sector, activity and macro sources.
   Existing shared news and supplemental calendars remain insufficient to claim
   complete discovery. Approve additional source integration separately if needed.
2. Build/review a new dated launch verifier/controller. It must verify exact
   commit/hash/deployment, all eleven services suspended/off, only staging DB
   destination, current masters, baseline counts/digests, indexes/audit triggers,
   no unfinished run/key or competing caller, and independently produced arming.
   Do not replace this with caller-supplied booleans or old markers.
3. Prove independent watchdog readiness before resume, suspension by 06:20 and
   independent all-eleven-off plus staging DB INACTIVE readback by 06:25. Preserve
   unresolved cleanup honestly. No after-window resume, retry, repair or rollover.
4. Resolve notification/escalation acceptance: missing/stalled run, consecutive
   failures and cleanup failure need observed delivery. Local watchdog and Codex
   share desktop/network risk. No unattended run without verified safeguards;
   otherwise require an available supervising operator or skip.
5. Obtain separate authorization for the exact publication/deployment, bounded
   rehearsal, credential reuse and a single dated hosted run. Existing October 13
   credential authorization expires at 08:00 Pacific and does not roll forward.

Proposed future window remains preparation 05:30, fresh checks after 05:40,
controller start 05:45–before 05:50, authenticated prerequisites by 05:55,
one scan POST during 06:00, no new fetching after 06:10, no writes after 06:15,
suspension at 06:20 and verified cleanup by 06:25 Pacific. Deadline failure means
skip/partial and cleanup, never extending the window. All other ten services,
especially production Discovery, schedules, consumer and executor, stay suspended.

Production schedules and ChatGPT weekday oversight tasks should remain paused.
Nothing in this local package changes their actual state.

## Reproduce offline tests

Use the existing bundled Python runtime and set PYTHONPATH to the existing
`../strategy-1-shadow-worker/.deps` directory. From this package run
`python -m pytest -q`. Tests have an autouse network block and invented credentials;
do not run hosted acceptance scripts or load encrypted credential helpers.

Recorded results and hashes are in
`../tooling/coordinator-acceptance-local-result-2026-10-13.json`.

## Subsequent local review, October 13

The initial 527-test result remains preserved as historical evidence. A subsequent
review reproduced eight failing regression cases and fixed five issue groups:

1. Prior-evidence envelope validation/hashing was repeated for each candidate.
   It now runs once for the candidate manifest. Independent snapshot comparison
   also precomputes its old-ID set instead of rebuilding it for every row.
2. Returning an existing run did not itself disable writes in the Controls layer.
   Only a newly acknowledged claim now grants write ownership; claim, persistence,
   finalization and per-symbol write attempts cannot be reused. Ambiguous writes
   consume their attempt and are never retried by this layer.
3. A successfully exhausted activity feed with no activity rows was reported as
   unavailable. It is now distinguished from retrieval failure while remaining
   incomplete for strategy discovery acceptance.
4. Launch-factory exceptions were outside the response-redaction boundary. They
   now fail closed with a fixed response code and no raw diagnostic response.
5. Malformed independent readback could raise instead of returning a failed
   verification. Invalid snapshot shapes now return MALFORMED_SNAPSHOT safely.

Latest review/test/hash evidence:
`../tooling/coordinator-review-result-2026-10-13.json`.
The initial failing tests are retained in
`../tooling/coordinator-review-before-fix-2026-10-13.xml`.
The reviewed source/coverage contract is `SOURCE-COVERAGE-CONTRACT.md`.
These changes do not install hosted admission or close the remaining source,
notification, real-database, deployment or watchdog acceptance gates.

## Source evidence follow-up, October 13

The local acceptance path now retrieves bounded SEC documents and provider news
content and persists traceable, review-required catalyst packets. Independent
readback checks their retained content and bindings. Final suite: 579 passed.
See `LOCAL-SOURCE-EVIDENCE.md` for limits, unverified gates and preserved initial
test-run errors, and `../tooling/catalyst-source-local-result-2026-10-13.json` for
the current result and exact hashes. The 527- and 537-test records above remain
historical evidence. Hosted admission is still locked and no deployment occurred.

## Local launch and source-review contracts

`LAUNCH-AND-REVIEW-CONTRACT.md` describes the next local implementation: exact
packet/citation-bound review inputs, dated admission guards and a durable one-attempt
controller core with explicit cleanup/notification outcomes. It also defines the
trust boundary. The historical controller-core result is preserved in
`../tooling/coordinator-launch-local-result-2026-10-13.json`.

## Local adapter and watchdog follow-up

Fixed-endpoint adapter classes, snapshot collectors, bounded driver and independent
watchdog process are now implemented and tested offline. `ADAPTERS-AND-WATCHDOG.md`
records their scope and remaining authentication, server-preflight and launcher
bindings. Hosted admission remains locked; no date is armed. Current evidence is
`../tooling/coordinator-adapters-local-result-2026-10-13.json`.

## Read-only preflight and rehearsal binding follow-up

`REHEARSAL-REVIEW-PACKAGE.md` is the current local implementation and hosted-review
proposal. The explicit rehearsal factory now provides authenticated, fixed-GET
preflight while leaving scanning locked. A separate no-scan rehearsal binding
checks independent suspension evidence and unchanged database snapshots. Hosted
connections, notification delivery and authorization remain unverified. No dates
or credentials were installed. Current test/hash evidence:
`../tooling/coordinator-preflight-local-result-2026-10-13.json`.
