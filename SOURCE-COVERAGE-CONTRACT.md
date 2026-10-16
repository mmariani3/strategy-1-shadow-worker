# Source coverage contract after local implementation review

Status: LOCAL CONTRACT / NOT HOSTED ACCEPTED. October 13, 2026.
No new source subscription, deployment, schedule, credential use or live test.

The live Rules v0.3, Experiment Plan v0.5 and Automation Specification v0.4
were read again during this review; revisions match the October 13 launch
authority record. Each master governs its own subject. This contract defines
engineering evidence, not new trade qualification or validation methodology.

## Separate acceptance decisions

1. **Reporting/storage correctness:** every required channel has an attributable
   attempt/outcome; unavailable or incomplete sources are preserved; retrieved
   data and candidates are faithfully persisted with audit and exclusion labels.
2. **Discovery protocol coverage:** the six required channels were actually
   checked using adequate source coverage, within the appropriate event window.
   A shared feed's exhaustion cannot certify coverage of all channel categories.
3. **Catalyst review readiness:** candidates have inspectable source content and
   event/symbol attribution, with unresolved contradictions explicitly retained.
4. **Strategy qualification:** explicitly outside this isolated acceptance.

A pass on (1) does not imply (2), (3), or (4). No fabricated catalyst, invented
event-time, raw-close substitution, numeric eligibility threshold, or automatic
major-event/tier/materiality decision may fill a gap. The live Journal remains
the system of record; this staging test does not complete its daily Scan Coverage.

## Channel inventory and required evidence

| Channel | Existing implemented path | Missing proof / completion requirement |
| --- | --- | --- |
| Earnings/guidance | Alpaca news keyword leads; SEC recent filing metadata for discovered symbols | Channel-specific collection scope spanning previous close/current premarket; original earnings/guidance content, issuer relationship and actual event date/time. A news update timestamp or filing date alone is insufficient. |
| Corporate news | Same news feed plus SEC metadata | Inspectable company/regulator/filing or credible report content; attributable company/event relationship. SEC lookup only after discovery is corroboration, not an independent whole-market discovery channel. |
| Analyst actions | News keyword leads | Attributable analyst firm, actual action, event date/time and source passage. Credibility/meaningfulness stays review-required; the implementation cannot infer it from the word analyst. |
| Sector/industry | News keyword leads; symbol-less stories now retained | Inspectable sector event and direct company relationship evidence. Stories with no ticker must remain in the funnel; no inferred company read-through. |
| Premarket activity | Bounded active non-OTC US-equity SIP collection, snapshots, separate dated raw prior evidence | Fresh universe/processed/unprocessed manifests and session/feed provenance; approved reference-price, instrument, unusual-volume and liquidity interpretation remain unresolved. A valid zero-activity response differs from source unavailability. |
| Scheduled/breaking macro | FRED, ISM, Forex Factory supplemental calendars; unassigned news retained | Explicit scheduled-source inventory and breaking-event review. Calendar checks cannot stand in for breaking coverage; provider impact labels cannot establish Strategy #1 major/imminent status. |

All attempts must retain source identifier, retrieval time, requested time range,
pagination/limit outcome, collected IDs, source URL/document identity, and a fixed
failure code when unavailable. Candidate counts must not include coverage-only
symbols. For an absent channel, store DATA_UNAVAILABLE with its reason, never
zero findings interpreted as completeness.

## Candidate evidence contract

For every discovered name preserve source-to-run-to-symbol lineage. Keep original
headline/publication/update fields and record whether underlying event timing and
symbol relationship were actually verified. Source content should be represented
by an attributable passage/document identifier and content hash under an approved
retrieval policy; a URL alone is not proof that the document supports the claim.

Cross-source comparison must evaluate the same event and issuer, contradictory
facts, and original source independence. Reprints of one release are not two
independent confirmations. Different SEC/news events for the same ticker remain
unmatched. A relevant filing does not automatically approve catalyst materiality.
The first hosted scope must end in REVIEW_REQUIRED, not automatic approval.

The local acceptance path now retrieves bounded SEC primary documents and directly
linked exhibit-99 documents, plus news content supplied by the existing Alpaca feed.
It persists content passages and hashes in run/symbol-bound review packets. These
are retrieval and structural-integrity checks; no semantic review is claimed.
The channel inventory above still describes discovery methods and their coverage
gaps: fetching a document for an already discovered name does not establish an
independent whole-market discovery channel. See `LOCAL-SOURCE-EVIDENCE.md` for the
exact limits and unverified conditions. No new hosted proof is established.
Do not select a paid provider or broaden credential scope without authorization.

## Explicit storage choice for the smallest next test

Keep existing run/item JSON and triggers; add no schema. Save the universe manifest
and collection outcomes once in the run, and separate dated evidence on discovered
leads. Do not create coverage-only candidates. This is enough to test normal
Coordinator lead persistence, but not a new full-universe per-symbol storage claim.
The October 13 full-universe ledger and all prior records remain untouched.

## Runtime and source budgets

One session/date, one new deterministic run key, and one scan POST. No resumed
IN_PROGRESS run or automatic replay. No source requests after 06:10; no database
writes after 06:15; independent suspension at 06:20 and all-eleven-off/DB-inactive
verification by 06:25 Pacific. Source/time/payload caps are operational limits,
never universe selection or strategy qualification rules. A truncated collection
is PARTIAL and retains what was not checked. Do not lengthen the window to pass.

## Go/no-go evidence matrix

| Gate | Current evidence | Before activation |
| --- | --- | --- |
| Local safeguards and persistence logic | Offline fixtures and regression suite | Review exact changed-file hashes and all unresolved findings. |
| Complete six-channel coverage | NOT VERIFIED; concrete gaps listed above | Implement/approve adequate collection/review sources and test actual coverage. Otherwise scope is only a partial integration test, which needs explicit acknowledgement. |
| Source-backed catalyst packet | OFFLINE structural/persistence checks PASS; hosted content and semantic review NOT VERIFIED | Verify direct-source availability and packet attribution, then review actual event/issuer relationship and same-event comparison without enabling qualification. |
| Real database/audit/concurrency | NOT VERIFIED for this Coordinator change | Fresh schema/index/trigger checks, before/after full digests, independent complete readback. Local fake store is not PostgreSQL proof. |
| Dated controller and admission | Controller, collector/adapter classes, independent watchdog/driver, read-only preflight and no-scan binding tested OFFLINE; actual authenticated host connections incomplete; exported app and all scan admission remain locked | Independently obtained exact-code/isolation/arming evidence and live watchdog/notification proof. See `REHEARSAL-REVIEW-PACKAGE.md`. No reuse of October 13 markers. |
| Watchdog/isolation/cleanup | October 13 proves the old isolated test only | New bounded no-scan rehearsal, independent watchdog ready before resume, actual all-eleven suspension/DB pause readback. |
| Notifications | Prior repeated-failure delivery unresolved | Observed missing/stalled/consecutive/cleanup-failure delivery and escalation. No unattended run on unverified delivery. |
| Credentials and hosted authorization | October 13 reuse expired at 08:00 Pacific | New bounded reuse authorization and separate exact deployment/run approval; do not reopen encrypted stores beforehand. |

The supervising Codex process is not an independent safeguard against the same
desktop/network failing. If mandatory notification/watchdog coverage is absent,
skip unattended activation. A supervised alternative needs an available operator
and separately agreed scope. No new resources or paid upgrades are assumed.

## Recommended sequence

Finish direct-source evidence/coverage work locally before choosing a hosted
date. Then prepare the dated controller and delivery/cleanup rehearsal for review.
Ask for exact deployment/rehearsal approval only when those artifacts are concrete.
Keep production schedules, the order-capable executor and weekday oversight tasks
paused throughout. No strategy validation or rollout phase advancement is implied.
