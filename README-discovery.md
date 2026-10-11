# Strategy #1 Discovery Coordinator

Phase-1 shadow discovery service for Strategy #1.

See [scheduled launch verification and missed-run reporting](README-discovery-scheduling.md) for the hardened scheduler, read-only watchdog, proposed hosted configuration and activation checks. This documentation does not enable a schedule or broker execution.

What it automates:
- Alpaca regular-session mover references (not current premarket activity).
- Bounded current-session SIP premarket minute bars across Alpaca's active US-equity universe, with snapshot quote/prior-close supplements and explicit collection gaps.
- Bounded, paginated Alpaca news collection, with incomplete coverage reported explicitly.
- Recent SEC EDGAR filing evidence for discovered U.S. symbols.
- Supabase discovery-run and candidate-funnel records.
- Scan Coverage status.
- Structured promotion into the existing Shadow Orchestrator after explicit review.

What it does NOT automate:
- Catalyst materiality judgment.
- Catalyst Tier A/B assignment.
- Cross-source verification judgment.
- Complete macro/economic calendar coverage. FRED and an ISM PMI supplement retain source evidence only; source failures and unresolved coverage remain visible.
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

The service never calls the Paper Executor or submits orders. Scheduled readiness uses the paper API's read-only market calendar.

## October 5 collection corrections (0.10.0)

The October 5 pilot collected prior-session movers and a capped news slice while feed-success flags looked like completed channel coverage. The implementation now keeps feed retrieval distinct from the full discovery protocol:

- News follows pagination tokens with one fixed start/end window, deduplicates article IDs, and retains earlier pages after a later failure. Requests stop after ten pages (at most 500 articles), a 45-second budget checked between requests, an error, or a repeated token. Each request has bounded connection/read timeouts; this is not a hard process deadline. No automatic request retries are added. Exhaustion of the provider's requested feed window is explicitly different from complete research coverage.
- Default lookback is 96 hours, with an allowed range of 1–168. This includes Friday afternoon in a normal Monday-morning request; it is not an event-freshness threshold or proof of holiday coverage. Existing explicit request bodies and `NEWS_HOURS` environment values still override the default. The earlier one-time pilot controller and deployed configuration are unchanged and must not be reused as a new launch authorization.
- News evidence retains `published_at`, `updated_at` and `feed_timestamp`. `event_timestamp` is null until separately verified. A small list of article symbols no longer automatically proves an issuer-specific catalyst. Original claims remain available; no evidence is promoted automatically.
- Mover values remain labeled regular-session references with `premarket_usable=false`. They cannot establish current premarket price, gap, activity, liquidity or the current soft price guideline. A true premarket discovery source remains a prerequisite for complete coverage.
- The ISM adapter reads only explicit target-month/year PMI dates, rejects ambiguous/changed pages and does not infer event time, DST, importance or imminence. It supplements FRED; neither an empty FRED response nor the combination proves a complete macro inventory. Forecast rows, other calendars and actual release outcomes are outside this parser.
- The Journal projection and scheduler no longer interpret old `CHECKED_ALPACA_*` / `CHECKED_FRED_*` feed flags as full channel completion. Source flags remain in the trace. Existing Journal rows and historical database records are not rewritten by this code change.

The new collector module is included in discovery implementation attribution. It uses existing JSON evidence/notes fields; there is no schema migration, new dependency, strategy-rule change or eligibility change.

### Verification and rollout limits

Offline tests cover pagination beyond 50, deduplication, later-page failure, caps, time budgets, redirects, malformed responses, stale event dates, calendar year/date ambiguity, retained leads, unchanged review gates, and conservative Journal/scheduler reporting. All tests block network access. The Python suite passed 201 tests on October 5, with the existing Starlette/AnyIO deprecation warning.

A separate public read-only ISM probe on October 5 returned HTTP 302 to `ecommerce.ismworld.org/SSO/Login.aspx`. A bounded normal public redirect check ended at HTTP 200 on that login page, not the calendar; no credentials were used. The adapter refuses that redirect and marks the source unavailable. Its parser is tested offline, but unattended source access is **not accepted**. The browser/search-accessible official calendar does not prove that a deployed Python service can fetch it.

Before another pilot: obtain a usable current-premarket source and an accessible, reviewed macro source; verify Alpaca paging/entitlements and the expanded collection's persistence duration under a bounded isolated acceptance plan; explicitly review lookback overrides; review the exact code revision and preserve independent suspension. Instrument-type screening also remains an explicit review requirement; all collected leads are retained. No deployment, service resume, scan, promotion, order, Journal delivery or recurring schedule is authorized by these local tests. Missing evidence from October 5 cannot be repaired by a retrospective scan.

Provider contracts checked October 5: [Alpaca news pagination](https://docs.alpaca.markets/us/reference/news-3), [regular-session movers](https://docs.alpaca.markets/us/reference/movers-1), and [ISM calendar](https://www.ismworld.org/supply-management-news-and-reports/reports/rob-report-calendar/).

## October 6 source-access results (0.10.1)

Read-only checks confirmed historical SIP premarket bars through the connected Alpaca account: five SPY one-minute bars for 12:55–12:59 UTC on October 6. SPY was used only as an infrastructure data probe, not a Strategy #1 candidate. Recent SIP bars and latest SIP quotes were rejected with the provider's subscription restriction; the connector reported a 15-minute delayed-access window. Live IEX quotes worked. IEX is a single-exchange source and cannot establish consolidated volume/spreads. These tests do not identify or verify the credentials saved in Render, establish a complete stock-screening universe, or retrospectively qualify a trade. No paid upgrade was made.

The [Forex Factory calendar](https://www.forexfactory.com/calendar) publishes a [weekly JSON export](https://nfs.faireconomy.media/ff_calendar_thisweek.json). An unauthenticated Python GET succeeded at 15:09 UTC on October 6: 82 events, 22 tagged USD, including the October 5 ISM Services PMI. The export's Last-Modified was 14:42:17 UTC. It is a secondary calendar with approximate/revisable times, not an official announcement or a completeness guarantee. The event fields were preserved for local infrastructure acceptance only.

The new supplemental adapter checks aware timestamps, the current Sunday–Saturday week in America/New_York, malformed or mixed/stale-week payloads, size limits and redirects. It retains all currencies for the requested date, removes exact duplicates, and flags repeated names with different times without selecting one. Provider impact labels remain separate from the unresolved Strategy #1 major/imminent judgment. No forecast or result is inferred. An empty day remains partial coverage, not an event-free assertion. The full Python suite passed 220 tests; all unit tests block network access. A separate live public GET through the adapter passed locally; hosted access and ongoing reliability remain unverified.

Other public access checks: BEA's release-schedule page and the Federal Reserve's FOMC calendar returned HTTP 200 with expected page markers. No full parsers or complete calendar acceptance were established for those pages. BLS's published iCalendar endpoint returned HTTP 403; no access workaround was attempted. ISM's direct calendar remains unaccepted following the October 5 login redirect. Source failures stay visible even when another supplement succeeds; the aggregate macro channel remains PARTIAL/REVIEW_REQUIRED.

All eleven Render services were read back suspended with automatic deployment off on October 6. Nothing was deployed, activated, scanned, promoted, ordered or journaled. The working calendar supplement resolves one source-access gap, but current consolidated premarket capability remains unavailable through the tested connector. Before a new prospective pilot, distinguish a limited discovery-only collection from full protocol completion, verify any chosen runtime data access and bounded persistence duration, and review the exact proposed code and configuration. Historical/delayed SIP can support appropriately labeled retrospective research under the governing Experiment Plan; it does not supply prospective live confirmation.

## October 7 premarket implementation (0.11.0, local only)

The October 6 entitlement result above is historical. After the user subscribed to Algo Trader Plus, the explicitly named Alpaca Paper Trading connector returned current SIP quotes/bars on October 7. A separate bounded read-only probe in the Discovery Render runtime also returned HTTP 200 for SIP quotes/bars at 15:27 UTC. The original production revision was restored and all eleven services were verified suspended at 15:32:51 UTC. Those checks establish runtime access, not acceptance of this new collector. This implementation has not been deployed.

Living Strategy Rules v0.3, Experiment Plan v0.5 and Automation Specification v0.4 were refreshed before implementation. No qualification, risk, catalyst, validation or execution rules change.

`premarket_collection.py` enumerates active `us_equity` assets independently of the news/mover list. It excludes explicitly OTC assets and retains other instrument types for review: Alpaca's asset class does not prove common-stock eligibility. An invalid, unknown-exchange, duplicate or oversized universe fails closed rather than silently narrowing it. The current trading session and exact prior session come from the paper API calendar; weekends/holidays are not guessed.

Only today's PREMARKET request between 04:01 and before 09:30 America/New_York is supported, also checked against the calendar open. One-minute SIP bars use an explicit fixed start at 04:00 and inclusive end just before the current minute. DST is handled by the time zone. Bars outside this interval, inconsistent OHLCV, malformed pages and conflicting duplicate timestamps stop collection. Exact duplicates do not double-count volume. There is no IEX/delayed fallback, request retry or redirect following.

Operational limits: at most 20,000 returned assets, 100 symbols per batch, 10,000 bars per page, 120 bar pages and a 120-second budget checked before each request. Per-request connect/read timeouts are at most 3/10 seconds. This is not a hard process deadline; slow response streams or processing can overrun it. Symbols are processed alphabetically. A cap can bias coverage toward early symbols, so results must never be presented as a market-wide ranking. The manifest retains the universe, completed batches, symbols without returned bars, unprocessed symbols, OTC exclusions and fixed outcome codes. No bars returned is not proof of no activity.

Each observed symbol retains bar count, observed volume, high/low, last completed bar close and timestamps. `premarket_volume` is populated only when its batch's feed is exhausted; otherwise only explicitly partial `observed_volume` is available. A successful snapshot can add a same-session quote/spread with its age, and an exact-prior-session unadjusted close/gap. Stale or crossed quotes and wrong-session closes are not accepted. Corporate actions can affect the unadjusted gap; it requires review. Age is reported without inventing a strategy freshness threshold. RVOL, ADV, unusual-volume and liquidity decisions remain null. Evidence is `REVIEW_REQUIRED`; `premarket_usable=false` prevents automatic qualification from these measurements.

Discovery merges all returned bar leads with existing news and regular-session references. The new evidence is stored separately under the existing `mover_snapshot.premarket_activity` JSON field; full collection metadata goes in run notes. No schema migration or dependency is added. The source file is included in implementation attribution. Runs/channel coverage remain PARTIAL/review-required even after feed exhaustion. Large Journal-preview notes become an explicitly labelled excerpt pointing to the complete unchanged discovery run; no Journal write is performed.

Verification: 257 offline tests passed, including 37 new premarket cases. All tests block network requests. Coverage includes broad-universe-only leads, DST, holidays, exact window boundaries, pagination, duplicate conflicts, malformed/partial pages, request/page/asset caps, SIP permission failures without fallback, stale/crossed quotes, exact prior-session gaps, separate persistence fields, conservative coverage projection and bounded Journal excerpts. One existing Starlette/AnyIO deprecation warning remains.

Before a pilot: accept this collector against real current-premarket responses, measure universe/page counts, response sizes, wall time and the larger funnel's SEC lookup/persistence duration under isolated bounded conditions; verify complete persisted item readback and manifest preservation. The existing per-symbol persistence path is not yet accepted for this larger volume. Macro coverage and review gaps remain. Reconcile the local branch against the deployed code, review the exact revision/configuration, and prepare a new date-specific plan with independent suspension. Do not reuse the expired October 5 controller or infer launch readiness from offline tests. No new pilot, deployment, recurring scan, order or Journal delivery was performed in this step.

Provider contracts: [stock bars](https://docs.alpaca.markets/us/reference/stockbars), [asset universe](https://docs.alpaca.markets/us/reference/get-v2-assets-1), [market calendar](https://docs.alpaca.markets/us/reference/legacycalendar), and [snapshot fields](https://alpaca.markets/learn/snapshot-api).

## October 9 throughput corrections (0.11.1, local only)

The October 9 hosted collector/storage attempt at commit `3ac73c4048265b573bd01f938536370ad2bdbff1` was PARTIAL and not accepted. It collected 3,689 items but stored and verified 575 before the 180-second persistence budget. The 13,241-symbol universe required at least 133 bar pages at 100 symbols per batch, exceeding the 120-page cap even before additional pagination. Collection stopped at 120 pages with 1,241 symbols unprocessed. All eleven services were independently verified suspended with auto-deploy off at 06:25 Pacific and the staging database was INACTIVE. Original terminal evidence remains unchanged.

This local revision uses 200-symbol batches while retaining the 120-page/120-second bounds, exact SIP window, pagination validation and partial manifests. More populated batches can still need multiple pages; provider latency can still exhaust the budget. This removes the guaranteed minimum-page mismatch without asserting complete coverage or a performance guarantee.

The isolated acceptance app now inserts arrays of at most 100 rows and 1 MiB encoded JSON, including per-row audit context, using the existing [PostgREST bulk insert contract](https://docs.postgrest.org/en/stable/references/api/tables_views.html#bulk-insert). There is no schema migration. The 180-second persistence and wall-clock gates remain. The storage item limit now matches the existing 20,000-asset operational bound instead of truncating at 3,000. A whole batch is acknowledged only after unique symbols and every submitted field match the returned rows; response ordering is irrelevant. A timeout, missing/duplicate row or mismatch stops further writes without retry or upsert. Subsequent paginated digest readback still verifies the complete stored item set. Fixed outcome codes distinguish time, item and payload limits from write ambiguity.

No prior close was accepted in the hosted premarket attempt. Its exact cause remains unresolved. A later regular-session SPY SIP snapshot through the paper connector contained the expected October 8 previous daily bar, but cannot reconstruct the earlier runtime responses or establish which credentials Render used. New diagnostics retain only parsed daily/previous-daily session dates and fixed unavailable reasons. The previous-close acceptance rule is unchanged: only the exact calendar-selected prior session is accepted, with unadjusted review-required labeling. No missing close or gap is inferred.

Verification: 290 application tests passed with network blocked, including 20 new cases for 13,241-symbol coverage in a one-page-per-batch fixture, 3,689-row bulk persistence/readback, reordered responses, missing fields, partial/duplicate responses, timeout ambiguity, item/byte/time limits and safe snapshot diagnostics. One existing Starlette/AnyIO deprecation warning remains. Fixture timings do not establish hosted throughput. Normal coordinator persistence is unchanged; bulk insertion applies only to the isolated acceptance app.

No deployment, database restoration, service activation, scan, acceptance replay, order or Journal write occurred during this local correction. All eleven services and the inactive staging database were rechecked after testing. The October 9 date, terminal attempt and controllers are preserved; source changes deliberately invalidate their old source-hash match. Before another attempt, review/publish an exact revision, conduct a separately authorized bounded hosted rehearsal of bulk persistence/audit/readback, and prepare a new date-specific plan with independent cleanup. The missing prior-close cause and complete news/SEC discovery pipeline remain unaccepted.

### October 10 storage rehearsal preparation

`storage_rehearsal.py` is a separate, staging-only application for one synthetic storage test. It exposes only health, authenticated preflight/result, and one run endpoint. Its window ends October 10 at 20:00 Pacific (October 11 03:00 UTC), with a 12-minute margin required before a run may start. The October 9 acceptance date, run key and expiry remain unchanged. The new deterministic `STORAGE_REHEARSAL|2026-10-10|PREMARKET|v0.3|INFRASTRUCTURE_TEST` key is distinct, and its unique database insert is the durable claim. Ambiguous claims/writes cannot be retried.

The fixed fixture contains 3,689 `ZZTEST` identifiers, synthetic metadata and 2 KiB padding per item. There are no prices, trade signals or market-data requests. Every item, run and audit context is explicitly infrastructure-only. The test exercises the same bounded bulk writer and paginated digest verifier as the proposed premarket acceptance, through explicit internal callbacks; old endpoint guards are not modified. Run state stays PARTIAL, and full discovery acceptance and Strategy #1 eligibility remain false even when all fixture rows persist correctly. Test rows and audit history are retained, not deleted after verification. Fixed padding tests JSON throughput without claiming to match the distribution of live evidence sizes.

The local October 10 controller requires an exact reviewed deployment/source manifest, fresh database/caller/master preflight evidence, renewed explicit credential-use approval, a durable local attempt marker, and a separate watchdog ready before resume. It permits only fixed staging resume/suspend and readback endpoints. A separate deployment-watchdog mode protects the separately reviewed deployment steps; it does not itself publish, deploy or change configuration. After the hosted test, independently check run/items/audit-event counts, suspend all eleven services, verify auto-deploy off, and pause the staging database. Provider or desktop outages can prevent cleanup and must be reported as unresolved.

Preparation verification: 303 application tests and 15 new desktop-control tests pass offline. A first desktop test invocation hit the existing Windows system pytest-temp ACL issue; a workspace-local fixture directory resolved it without changing runtime guards. The actual deployment, hosted storage/audit performance, independent watchdog behavior and final database reconciliation for this rehearsal remain unverified until execution. No October 10 credentials have been decrypted or renewed by preparation alone. See workspace `tooling/october10-rehearsal-plan.json` for actual readiness; no automation is armed by these files.
