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
- At most one scan POST per invocation. Concurrent invocations still rely on the existing database unique run key. Transport failures are reconciled by GET, never automatically redispatched. An existing unfinished run is reported, not resumed/recreated.
- Readback checks identity, aware timestamps, intended launch minute, phase, persisted item count and coverage. Premarket completion after the open is explicitly flagged. Strict request/response clock ordering fails closed on clock disagreement; no numerical data-freshness policy is invented.
- `AUDIT` only uses GET. It reports the missing expected run even when the launch job never ran, provided the audit job itself runs. It never repairs a missed scan by backdating or launching one.
- Structured JSON output contains status, UTC observation time, scheduler version, run key/ID and coverage gaps. Raw HTTP responses, exception bodies and credentials are not printed. The readback endpoint also supplies the coordinator implementation and persisted transition attribution.

## Outcomes and notification behavior

| Outcome | Meaning | Exit |
|---|---|---:|
| `COMPLETED` | Exact persisted run is COMPLETE, counts/timing agree and coverage has no unresolved channel | 0 |
| `COLLECTED_REVIEW_REQUIRED` | Collection persisted as PARTIAL; full Scan Coverage is not complete | 1 |
| `MISSED_RUN` | Audit found no expected run | 1 |
| `RUN_UNFINISHED` | Expected run is still IN_PROGRESS | 1 |
| `MISSED_LAUNCH_WINDOW` | Launch cannot safely occur in the configured minute | 1 |
| `RUN_OUTSIDE_SCHEDULED_MINUTE` | Persisted run does not match intended operational launch time | 1 |
| `PREMARKET_NOT_FINISHED_BEFORE_OPEN` | Persisted finalization was after the market opened | 1 |
| `DISPATCH_OUTCOME_UNRESOLVED` | Single submission had no verifiable persisted result | 1 |
| Other validation/dependency failures | Explicit uncertainty, mismatch or unavailable data | 1 |
| `CONFIGURATION_ERROR` | Required configuration invalid/missing | 2 |
| `WEEKEND`, `MARKET_CLOSED`, `OTHER_DST_INVOCATION` | Explicit expected non-dispatch | 0 |

`DISPATCH_INTENT` and `WARMED_WAITING_FOR_LAUNCH` are intermediate events, not successful scan outcomes. The process exit/final event controls the result.

The coordinator currently finalizes raw discovery as PARTIAL because human/structured verification remains outstanding. Expect `COLLECTED_REVIEW_REQUIRED`; it must not be disguised as complete. Nonzero exits surface these conditions in job history and can trigger provider failure notifications. **Notification recipients and delivery must be verified before activation.** A healthy HTTP response is not an alert delivery test.

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
3. Verify one deliberate job failure reaches the intended user through provider notifications, and verify the watchdog still reports a missing run when its launcher is disabled. A test performed only by reading logs does not establish delivery.
4. Confirm coordinator availability during warm-up. The suspended/free service must actually be resumed and reachable; health checks cannot undo an administrative suspension.
5. Approve the concrete activation configuration/cost, then enable discovery-only operation for a real prospective session. Keep execution components disabled. Independently check actual completion, coverage and notification receipt. No production activation is part of this PR.

Read-only counts use the existing Data API selection helper. If a provider row limit truncates a very large funnel, the count mismatch fails closed; pagination is a remaining limitation, not inferred success. The calendar/scheduler check does not improve the underlying source provider's coverage or finish qualitative catalyst review.

## Validation

Run `python -m pytest -q tests/test_discovery_scheduler.py tests/test_discovery.py tests/test_journal.py` with repository dependencies installed. Tests block live network access. They cover exact-key API authentication, missing/stalled/partial runs, ambiguous POST delivery, stale readback, wrong identities/classes/phases, secret-safe failures, cold starts, warm-up/oversleep, DST, holidays, early closes, persistence discrepancies and inconsistent completion claims.

References: [Render cron execution and pricing](https://render.com/docs/cronjobs), [Alpaca calendar endpoint](https://docs.alpaca.markets/us/v1.1/reference/getcalendar-1), [PostgREST table reads](https://docs.postgrest.org/en/v14/references/api/tables_views.html).
