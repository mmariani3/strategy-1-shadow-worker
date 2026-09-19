# Code checks before model review

This offline research stage checks every captured discovery record without a model call. It preserves the full funnel and identifies missing evidence before spending on interpretation. It does not call the Strategy Worker, create decisions, qualify candidates, confirm triggers, write the Journal or access a broker.

The governing masters remain Strategy Rules v0.3, Experiment Plan v0.5 and Automation Specification v0.4. Their living revisions were re-read on September 18, 2026 before implementation. Nothing under `sources/` is modified. No new numerical strategy threshold or observation eligibility is introduced.

## Run without API credentials

From the repository, using the existing development/journal dependencies:

```text
python run_code_review.py --bundle PRIVATE_BUNDLE.json --output PRIVATE_OUTPUT
```

The bundle is an immutable output from `evidence_pipeline.py`. The command validates its complete source funnel, produces a content-addressed JSON report, and prints only counts and an artifact path. It never sends a request. Existing artifacts are never overwritten. `--checked-at` permits an explicitly timestamped offline replay; omit it to record the actual check time. All results remain historical research, not a refreshed live review.

`--review-slots N` optionally proposes N records for later research, in stable discovery-item-ID order. It is **not** a quality ranking, strategy filter, spend authorization or dollar cap. The default is zero; other records remain `DEFERRED_BUDGET_UNREVIEWED`. The existing API client still requires explicit dispatch, selected model and its separate persistent call budget. This planner does not dispatch or enforce that budget.

## What code checks

| Check | What it establishes | What remains unresolved |
| --- | --- | --- |
| Full discovery funnel, original source digests/text, linked IDs, authority revisions | Internal consistency, missing/duplicate records and changed evidence | Authenticity of the original capture and current live master state |
| Captured source inventory | News text versus absent evidence or filing metadata without document text | Actual catalyst, materiality/tier, source independence and same event |
| Required structured fields, strict booleans and approved labels | Missing, malformed and explicitly supplied inputs | Truth of a prior review assertion |
| Directional entry/stop/target geometry | Positive prices, risk/share, reward/share and R/R | Structural invalidation and meaningful target choice |
| Risk arithmetic | 1.5R floor; 1.5–2R needs clean-structure review; floor sizing under $50 risk and $10,000 notional ceilings | Current risk budget, account state and actual position selection |
| Daily counters | Supplied $100 daily loss / 3 executed trades limits | Live account refresh and counter provenance |
| Timestamps and explicit review interval | Timezone/order and existing review contract consistency at capture | New freshness durations, actual catalyst-event time or renewed approval |
| Consolidated-data declarations | Missing required declaration or explicit IEX/consolidated contradiction | Feed entitlement, real-time status and reliable measurements |
| Negative assertions | Failed liquidity, missed trigger, invalid target, adverse context remain visible | No assertion is silently turned into a generic trigger wait |

`PASS` applies **only to the named mechanical check**. It never means a complete Strategy #1 criterion passed. All 11 research criteria remain semantically unresolved; prior booleans are `RECORDED_ASSERTION`. Sources from qualification, setup, candidate and signal stages are inspected separately rather than silently merged. In particular, the code does not invent direction for a setup artifact that lacks it; geometry then remains unresolved until supplied in an attributable contract.

Risk calculations are research arithmetic under the documented hard ceilings, independent of deployment environment overrides. They do not select a quantity for a live handoff. A correctly formatted old timestamp does not mean fresh data. Filing dates and news publication/update times do not establish the underlying catalyst's freshness. A price crossing never becomes confirmation.

## Routing and cost control

The [public source collector](README-source-collection.md) can add later-retrieved document text in a new, explicitly linked research packet. The original packet and its discovery time are preserved. `retrieved_document` sources are inventoried like captured news/filing text; this changes source availability only, never semantic qualification.

- `EXCLUDED_INFRASTRUCTURE`: preserve classification and exclude from ordinary strategy research requests.
- `NEEDS_SOURCE_EVIDENCE`: no captured news/filing text to interpret. Retrieve evidence first. This is not a rejection or proof of no opportunity.
- `REVIEW_REQUIRED`: some captured text exists; qualitative review remains necessary. Text presence says nothing about relevance, credibility or sufficiency.

The single-packet `run_research_reviewer.py` entry point now runs these checks first and stops the first two routes before loading credentials, reserving a call or preparing a model request, including when `--dispatch` is supplied. Direct low-level library callers are not changed by this CLI guard. A future hosted service must explicitly adopt the same gate before rollout. No hosted integration is claimed here.

Existing exact-request caching, retry/concurrency barriers and call limits remain in `review_attempts.py`. This change never reuses a qualitative approval across candidates or refreshes one from unchanged text. It does not silently shorten the governing master documents or add an AI score/keyword filter.

The full captured September 18 scan contains 112 records: 74 have some captured news text; 38 require source evidence first (25 without a catalyst source, 13 with filing metadata only). All 112 remain in the local report. At zero proposed slots all 74 are budget-deferred/unreviewed. This avoids **38 premature review requests** relative to sending every record immediately, not 38 completed reviews or guaranteed lifetime savings. Evidence retrieval and later reviews may still cost money. The scan is PARTIAL, there are no structured candidate/setup reviews in this capture, and opportunity count remains UNKNOWN.

## Verification and boundaries

Run `python -m pytest -q`. Regression cases cover full-funnel loss/duplication, altered sources/lineage, infrastructure exclusion, metadata-only evidence, injection, preserved negative assertions, numeric and R/R boundaries, notional-limited sizing, fractional/invalid counters, non-finite numbers, timezone/future timestamps, expired review intervals, false consolidated declarations, and CLI refusal before credentials/network access.

No schema migration is required. No production service, schedule, model selection or billing configuration is changed. Phase 1 remains SHADOW, with broker execution disabled. Journal state is explicitly `NOT_CHECKED`; this report is not a Sheet readback or Strategy #1 executed observation.
