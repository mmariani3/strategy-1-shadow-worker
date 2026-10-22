# Local launch safeguards and structured source review

October 13, 2026. LOCAL / NOT ARMED / HOSTED ADMISSION DISABLED.

The living Rules v0.3, Experiment Plan v0.5 and Automation Specification v0.4
were refreshed through Google Drive. Revisions match the previous review;
the exact IDs/revisions/read time are in
`../tooling/coordinator-launch-authorities-2026-10-13.json`. No master was changed.
Sources, accepted October 13 records and the original implementation are preserved.

## Source-review contract

`catalyst_review_contract.review_record` validates a separate infrastructure-only
review record bound to the exact run, symbol and catalyst packet hash. Required
findings cover event identity, issuer relationship, event time, source relationship,
contradictions, analyst attribution and sector relationship. Each finding records
SUPPORTED, DISPUTED, UNKNOWN or NOT_APPLICABLE, a rationale, and citations into
retained source text. Supported/disputed findings require exact source IDs,
character offsets and matching passage hashes. Unknown information remains unknown.

These are reviewer assertions. A correct citation does not prove the interpretation.
The local contract does not authenticate the reviewer, infer a catalyst, classify
materiality, impose a new source-count threshold, approve raw reference prices or
approve a trade. A same-symbol match is not a same-event match. Reprints are not
independent confirmation. Required qualitative judgments still need explicit review
under the governing masters. User-authenticated review ingestion is a separate gate.

Permitted review dispositions are REVIEW_REQUIRED and REJECT_EVIDENCE. Rejection
retains the record and reason; it does not delete the lead or rewrite its history.
Even a structurally valid, fully supported submission leaves candidate state
REVIEW_REQUIRED, qualification/promotion disabled and strategy eligibility false.
This contract is offline only and is not yet a hosted review route or database write.

The six-channel inventory and coverage gaps in `SOURCE-COVERAGE-CONTRACT.md` still
apply. Completion of the review schema does not accept channel coverage or semantic
catalyst accuracy. Unavailable-channel reporting, source provenance, candidate
traceability and record preservation are measurable engineering gates; complete
discovery remains a separate decision under the Strategy Rules and live Scan Coverage.

## Controller core and trust boundary

`coordinator_launch_guard.py` checks a separately pinned, immutable policy against
observed data. `coordinator_acceptance_controller.py` implements bounded transitions
using injected adapters. It contains no networking, credential loader, process
launcher, deployment action, scheduling action, selected hosted date or executable
hosted run mode. Running the module exits with HOSTED_RUN_DISABLED. The exported
web app remains locked; no factory has been connected to the controller.

Adapter classes and a separate process launcher were subsequently implemented;
see `ADAPTERS-AND-WATCHDOG.md`. All verification calls remain offline fixtures.
Supplied JSON, a PID field,
an authorization ID, a digest, or a flag is not proof of authorization or reality.
Before deployment, authenticated collectors must actually read the approved Render
workspace, complete Supabase snapshots/schema/index/trigger inventories, living
masters, caller inventories and pinned rehearsal artifacts. They must verify the
independent arming producer and real watchdog process identity, program hash,
heartbeat and suspension authority. Freshness applies to the entire evidence bundle;
collectors must not relabel old records with a new timestamp. Schema hashing must
cover all required indexes and audit-only functions/triggers, not an arbitrary subset.

The offline core requires all eleven exact service IDs, correct workspace, all
auto-deploy off, all other services suspended, exact deployment/commit/source hash,
the full required local file-hash inventory, unchanged master revisions, staging DB
ACTIVE_HEALTHY, reviewed schema hash, absent exact run key, no unfinished runs,
no conflicting schedules/processes/pg_cron callers and complete baseline digests.
Baseline differences block dispatch; they are never overwritten to make admission pass.

The pinned no-scan rehearsal must belong to the same date/code/deployment, contain
independent watchdog suspension evidence, all-eleven-off/DB-inactive cleanup, and
five distinct recipient-confirmed notification cases: missing run, stalled run,
first failure, consecutive second failure, and cleanup failure. Provider acceptance
alone is insufficient. The receipt references must resolve to independently verified
evidence within the approved package; fixtures are not delivery acceptance.

## Fixed operational sequence

| Stage | Local core behavior | Required future operational proof |
| --- | --- | --- |
| Preparation | Start only 05:45–before 05:50 Pacific; current evidence from at/after 05:40 and at most 120 seconds old; date and authorization through cleanup checked. | An external preparation driver starts at 05:30 and restores only the approved staging DB. No late restoration deadline extension. |
| One attempt | Exclusive-create/fsync marker keyed by deterministic run key, independent of changed code/manifest; crash/partial marker consumes the attempt. | Protected local evidence directory, filesystem durability and same-host concurrent-process rehearsal. Never erase a marker or retry on another date. |
| Watchdog/resume | Matching nonce/policy/service, distinct PID, recent heartbeat and exact 06:20/06:25 deadlines before staging-only resume. Resume timeout is ambiguous and triggers cleanup. | Real independent process verified from OS/provider readback; monotonic deadline and bounded network timeouts. A PID supplied in JSON is insufficient. |
| Readiness | Exact runtime identity, SHADOW, broker/qualification/Journal disabled; authenticated paper-calendar/SIP/historical-SIP/staging-DB probes before 05:55. | Actual read-only authenticated probes, never health alone. |
| Dispatch | Fresh active isolation/baseline/runtime/watchdog checks; exclusive durable POST intent; one normal `/scan/run-once` POST only 06:00:00–06:00:59. | A reviewed fixed-endpoint adapter. Timeout never authorizes replay. |
| Readback | HTTP success is not acceptance. Independently obtained complete before/after snapshots must match launch baseline and pass existing record/audit/packet verifier. | Read-only repeatable snapshot/export with complete pagination, independent counts and protected-table coverage. |
| Cleanup | At/after 06:20 request staging suspension, independently verify all eleven suspended/off, then pause DB and verify INACTIVE. Stop watchdog only after verified cleanup. Record whether 06:25 was met. | Driver remains active; independent watchdog acts even if driver dies. Live suspension/status and DB-pause readback remain unverified for this package. |

The core advances on explicit ticks; it is not a background scheduler. A future
driver must tick regularly and bound every adapter call. The independent watchdog
must enforce the deadline when the driver, wall clock or network fails. No software
claim here eliminates shared desktop/provider/network failure risk.

Source fetch and database-write limits remain 06:10 and 06:15 in the Coordinator
controls. No after-window resume is allowed to recover missing evidence. If service
suspension cannot be verified, the core retains the watchdog and does not pause DB
under an unverified writer. Cleanup failure remains UNRESOLVED. A duplicate controller
cannot interrupt the existing attempt's cleanup. A controller without attempt
ownership cannot perform cleanup mutations. Separate authorized recovery remains
necessary if evidence ownership or credentials are unavailable.

Notification failure cannot prevent cleanup. Send-returned is recorded as delivery
unverified, never successful receipt. Outcomes are stored separately without replacing
the original attempt/result. No email or other message was sent during this work.
Unattended operation remains blocked until actual delivery and safeguards are proven.

## Acceptance and next authorization

PASS locally means adverse fixtures block activation/dispatch as intended, concurrent
starts produce at most one activation, ambiguous POST never replays, normal Coordinator
fixture persistence passes independent readback, and cleanup failures remain explicit.
It does not mean hosted admission or Phase 1 is accepted. Fixtures are infrastructure
tests, never experimental observations. No broker or Journal action is permitted.

The smallest next implementation is the authenticated collector/adapter and bounded
driver integration, reviewed and tested offline first. Then obtain authorization for
one exact deployment and no-scan rehearsal, including a fresh, bounded credential
reuse period and notification test delivery. A single dated collection attempt needs
its own verified readiness/arming after that rehearsal. Do not choose or arm a hosted
date from the test fixtures. October 13's expired credential permission is not reused.

Source sufficiency, semantic review/authentication, real PostgreSQL audit/concurrency,
live watchdog/notification reliability and the full execution/monitoring/Journal
lifecycle remain unresolved. Production schedules and ChatGPT weekday oversight
should remain paused. Phase 1 is not accepted; Phase 2 is not ready.

Final test results, exact changed-file hashes and original-file preservation checks:
`../tooling/coordinator-launch-local-result-2026-10-13.json`.

Final full suite: 645 passed (66 new controller/review cases), with one existing
Starlette/AnyIO deprecation warning. The initial targeted run is retained: ten
review tests passed, while 49 controller fixtures errored because Windows denied
access to the shared pytest temp directory. Fresh workspace fixture directories
resolved that test-environment issue. Later targeted/integration runs and both
full-suite XML results remain preserved. No fixture error was counted as a pass.
An explicit local `--run` check exited with the expected hosted-disabled code.
