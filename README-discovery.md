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
