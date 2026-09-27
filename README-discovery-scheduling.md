# Reliable discovery launches and visible missing runs

This change is infrastructure-only, based directly on main `7ea7c1170759c9536dc4f61c55da017390aebf08`. It does not depend on research/presentation draft PRs. Strategy v0.3, Experiment v0.5 and Phase 1 SHADOW remain unchanged. No orders, automatic promotion, invented freshness threshold or Journal writes are introduced.

## Problem addressed

The old runner returned success for any response containing a run ID, including an `IN_PROGRESS` replay. It also returned success for every off-time invocation, without determining whether today's scan was missing. A paused job cannot report its own absence.

The September 18 supervised chat attempt missed its launch window; a later POST_OPEN collection did not replace the absent premarket scan. Hosted execution must be independent of chat availability. A schedule is not evidence that a run happened.

## Behavior

- `RUN` optionally starts early, checks SHADOW health, waits inside its hosted process, rechecks health, then reads the session calendar and exact expected run key. `WARMUP_MINUTES=5` permits starting five minutes before the existing launch minute; it does not permit late scans. This is an operational configuration, not a catalyst age or strategy eligibility rule.
- The launch date uses the configured local timezone, including DST. An invocation from the other configured UTC offset is explicitly identified. Unexpected late launches fail visibly. A slow dependency or oversleep cannot silently move submission outside the launch minute.
- The paper API market calendar handles holidays and early closes. It is an authenticated read-only `GET /v2/calendar`, never a broker submission. Errors/malformed data are unavailable, not holidays. Dates outside the provider's documented 1970–2029 coverage fail closed.
- A new authenticated `GET /runs/scheduled?session_date=...&phase=...&run_class=...` looks up the exact deterministic run key. Yesterday's run, another phase or an infrastructure run cannot satisfy a Strategy #1 run.
- At most one scan POST per invocation. Concurrent invocations still rely on the existing database unique run key. Transport failures are reconciled by GET, never automatically redispatched. An existing unfinished run gets bounded read-only checks, never a resume/recreate request.
- Readback checks identity, aware timestamps, intended launch minute, phase, persisted item count and coverage. Premarket completion after the open is explicitly flagged. Strict request/response clock ordering fails closed on clock disagreement; no numerical data-freshness policy is invented.
- `AUDIT` only uses GET. It reports the missing expected run even when the launch job never ran, provided the audit job itself runs. It never repairs a missed scan by backdating or launching one.
- Structured JSON output contains status, UTC observation time, scheduler version, run key/ID and coverage gaps. Raw HTTP responses, exception bodies and credentials are not printed. The readback endpoint also supplies the coordinator implementation and persisted transition attribution.

## Outcomes and notification behavior

| Outcome | Meaning | Process exit |
|---|---|---:|
| `COMPLETED` | Exact persisted run is COMPLETE, counts/timing agree and coverage has no unresolved channel | 0 |
| `COLLECTED_REVIEW_REQUIRED` | Collection persisted as PARTIAL; full Scan Coverage is not complete; awaiting review is expected | 0 |
| `MISSED_RUN` | Audit found no expected run | 1 |
| `RUN_UNFINISHED` | Expected run is still IN_PROGRESS | 1 |
| `MISSED_LAUNCH_WINDOW` | Launch cannot safely occur in the configured minute | 1 |
| `RUN_OUTSIDE_SCHEDULED_MINUTE` | Persisted run does not match intended operational launch time | 1 |
| `PREMARKET_NOT_FINISHED_BEFORE_OPEN` | Persisted finalization was after the market opened | 1 |
| `DISPATCH_OUTCOME_UNRESOLVED` | Single submission had no verifiable persisted result | 1 |
| Other validation/dependency failures | Explicit uncertainty, mismatch or unavailable data | 1 |
| `CONFIGURATION_ERROR` | Required configuration invalid/missing | 2 |
| `WEEKEND`, `MARKET_CLOSED`, `OTHER_DST_INVOCATION` | Explicit expected non-dispatch | 0 |

`DISPATCH_INTENT`, `WARMED_WAITING_FOR_LAUNCH` and `READBACK_RETRY` are intermediate events, not successful scan outcomes. Inspect the final event's `outcome` and `discovery_complete` for scan completion. Process exit means whether the operational workflow needs attention; it is not proof of complete research.

The coordinator currently finalizes raw discovery as PARTIAL because human/structured verification remains outstanding. Scheduler 0.4.0 handles this as an expected research-review state: process `exit_code=0`, `assessment_exit_code=1`, `discovery_complete=false`, `notification_route=NONE`. Stored collection remains PARTIAL; nothing approves a catalyst or trade. Do not use a green job badge or zero process exit as evidence of complete Scan Coverage. Unresolved operational failures retain nonzero process exits and `notification_route=FAILURE`, which can trigger configured provider failure notifications. **Notification recipients and delivery must be verified before activation.**

### Automated operational response

The scheduler now carries out the safe follow-up checks without requiring the user to request them:

1. Health checks retry transport errors and HTTP 408/429/5xx at most four times with delays 0, 2, 5, 10 seconds. Authentication failures, malformed replies and failed safety settings stop immediately.
2. Before submission, readback retries temporary transport/HTTP failures at most three times with delays 0, 2, 5 seconds. The launch minute is checked again afterwards; retries cannot authorize a late scan.
3. After the single POST attempt, automatically read back at most three times for temporary failures, an absent run or IN_PROGRESS. Existing runs and AUDIT use the same bounded reconciliation. The initial valid read counts as the first attempt when reused. No POST is repeated.
4. Every reply must pass the original identity/freshness checks. A saved run disappearing or changing ID fails closed. Permanent HTTP errors and invalid data do not get retried until a more favorable result appears.
5. If the result is verified COMPLETE or expected PARTIAL, finish without requesting a failure notification. PARTIAL stays pending review. If automatic checks cannot resolve the problem, record the exact outcome and request failure notification through the nonzero job exit.

These retry delays are infrastructure backoff, not strategy freshness thresholds or permission to trade. HTTP timeouts still apply to each attempt. A retry event is logged before each follow-up GET; raw exceptions and secrets are omitted. There is no model/API inference cost for this deterministic workflow.

A missed launch cannot be repaired prospectively, so the invocation skips submission and still reports an operational failure for investigation. An audit rechecks a missing run before escalating it. The user is not expected to place a trade, chase an opportunity or manually press retry. Without an operator response, no repair is attempted; later enabled jobs independently repeat their safety checks.

### What to do when an alert arrives

Every JSON event includes a deterministic `response` object: policy version, category, event stage, plain-language summary, action already taken by this invocation, user action and when it is needed. `discovery_alerts.py` contains policy 1.1.0 and remains a pure guidance function; `discovery_scheduler.py` performs the bounded reconciliation above. Unknown outcomes require investigation and cannot emit a zero exit code.

| Alert category | Your response | Scheduler behavior |
|---|---|---|
| `MISSED_SCAN` | Send the alert for investigation when convenient. No need to rush or chase an opportunity. | Reports the missed scan; no late replacement. |
| `RECONCILE` | Automatic checks could not resolve the result; request investigation before reliance. Do not press retry. | Performs bounded GET reconciliation first; an in-flight request may still finish. No POST replay. |
| `MAINTENANCE` | Have configuration, safety settings or saved evidence checked before relying on the pipeline. | Fails the current invocation. An unavailable/unsafe dependency is not presumed harmless. |
| `TIMING_REVIEW` | Review actual timestamps and coverage rules before using the research. | Flags wrong/late timing and preserves the original records. |
| `RESEARCH_REVIEW` | No failure notification requested. Research can await review; leave it unreviewed if unavailable. | Keeps raw discovery PARTIAL; no catalyst qualification or trade approval. |
| `INFO` / `PROGRESS` | No response to this event. Progress still needs a final result. | Reports an expected skip, verified discovery completion, or intermediate activity. |

For example, a `MISSED_LAUNCH_WINDOW` event says: **The permitted scan launch minute was missed. Skipped submission; did not launch a late replacement.** Its response timing is `WHEN_CONVENIENT`. A submission timeout triggers automatic read-only reconciliation. Only an unresolved final result requests investigation, because the remote request might still be running.

These instructions apply only to discovery. They do not manage open positions or verify that every other service is disabled. Emitting an alert does not pause future scheduled jobs, repair configuration, obtain human approval, trigger Codex follow-up, or send a separate notification. Automatic read checks happen before the final event; they do not continue indefinitely awaiting the user. Research is not approved by silence.

Provider notifications may contain only a failure notice and a link to logs; the structured guidance is in those logs. Routing uses the process exit only; no separate notification sender was added. Acceptance must verify where the user actually sees the guidance and that routine PARTIAL outcomes do not trigger failure notices. Custom email rendering, digests, cross-run deduplication, consecutive-failure tracking and a persistent pause/reset mechanism are not implemented. Unresolved failures remain visible on each invocation rather than being silently suppressed across sessions. Until receipt is tested, do not claim that notifications reach the user's inbox.

## Proposed hosted configuration — NOT activated

Use the existing premarket Render job, plus an independently scheduled audit invocation. No service, paid resource, notification destination or schedule is created by this commit.

| Setting | Premarket launcher | Read-only premarket watchdog |
|---|---|---|
| Command | `python discovery_scheduler.py` | `python discovery_scheduler.py` |
| Action | `SCHEDULER_ACTION=RUN` | `SCHEDULER_ACTION=AUDIT` |
| Phase/class | PREMARKET / STRATEGY_1 | PREMARKET / STRATEGY_1 |
| Local launch/audit time | `LOCAL_HOUR=6`, `LOCAL_MINUTE=0` | `LOCAL_HOUR=6`, `LOCAL_MINUTE=15` |
| Expected scan time | `SCAN_LOCAL_HOUR=6`, `SCAN_LOCAL_MINUTE=0` | `SCAN_LOCAL_HOUR=6`, `SCAN_LOCAL_MINUTE=0` (both required) |
| Warm-up | `WARMUP_MINUTES=5` | `WARMUP_MINUTES=0` |
| UTC weekday schedule | `55 12,13 * * 1-5` | `15 13,14 * * 1-5` |

Both use `LOCAL_TIMEZONE=America/Los_Angeles`, `RULESET_VERSION=v0.3`, explicit HTTPS `DISCOVERY_URL`, and a privately configured `DISCOVERY_SCHEDULER_TOKEN`. The launcher's existing mover/news settings should be preserved unless separately approved. The watchdog minute is a proposed operational reporting deadline; it changes neither strategy freshness nor observation eligibility. A delayed AUDIT invocation after its target still audits that day's run (except the explicitly paired DST invocation).

The existing post-open schedule is not enabled by this work. To use this runner for it, configure the phase and both scan-time fields explicitly. A post-open scan cannot substitute for a missed primary scan, and collection lookback does not certify event novelty.

On Render, a separate cron watchdog has a $1/month minimum and shares Render's failure domain. An external runner can use the same AUDIT command, but its scheduling, secrets, costs and notifications must be configured and verified separately. No monitoring process can report its own total absence; provider-wide outages require an external heartbeat/uptime check. This implementation does not claim that coverage.

## Activation sequence and remaining verification

1. Review/merge this isolated change, deploy coordinator and launcher to staging, and verify the exact installed implementation versions. No schema migration is needed; the read endpoint reuses existing tables and authentication.
2. Use isolated `INFRASTRUCTURE_TEST` staging fixtures for missing, unfinished, partial and completed states. Verify the read endpoint's calendar entitlement and persisted readback against the actual provider; local mocks do not establish either. Never inject synthetic records into production as STRATEGY_1.
3. Verify a transient read failure resolves without a failure notification; an unresolved failure reaches the intended user with accessible guidance; expected PARTIAL has a zero process exit while preserving incomplete coverage; and the watchdog still reports a missing run when its launcher is disabled. A test performed only by reading logs does not establish delivery or notification suppression.
4. Confirm coordinator availability during warm-up. The suspended/free service must actually be resumed and reachable; health checks cannot undo an administrative suspension.
5. Approve the concrete activation configuration/cost, then enable discovery-only operation for a real prospective session. Keep execution components disabled. Independently check actual completion, coverage and notification receipt. No production activation is part of this PR.

Read-only counts use the existing Data API selection helper. If a provider row limit truncates a very large funnel, the count mismatch fails closed; pagination is a remaining limitation, not inferred success. The calendar/scheduler check does not improve the underlying source provider's coverage or finish qualitative catalyst review.

## Validation

Run `python -m pytest -q tests/test_discovery_scheduler.py tests/test_discovery.py tests/test_journal.py` with repository dependencies installed. Tests block live network access. They cover exact-key API authentication, missing/stalled/partial runs, ambiguous POST delivery, stale readback, wrong identities/classes/phases, secret-safe failures, cold starts, warm-up/oversleep, DST, holidays, early closes, persistence discrepancies and inconsistent completion claims. Alert tests require explicit guidance for every emitted outcome and verify missed-scan response timing, safety escalation, read-only reconciliation, preservation of PARTIAL results, intermediate/final distinction and unknown-outcome failure.

References: [Render cron execution and pricing](https://render.com/docs/cronjobs), [Alpaca calendar endpoint](https://docs.alpaca.markets/us/v1.1/reference/getcalendar-1), [PostgREST table reads](https://docs.postgrest.org/en/v14/references/api/tables_views.html).
