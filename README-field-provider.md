# v22 targeted ADMA provider test

## Result

One complete GPT-5.5 v22 response was admitted as a research draft. Separate
source review still requires revisions. Structural admission does not establish
source correctness, catalyst qualification or eligibility for a trading handoff.

This is a targeted repeat of the preserved ADMA source previously tested with
v21. It is neither a new unseen source nor a general model-accuracy benchmark.
The original response, failures, source-first reference and earlier assessments
are preserved without repair or retrospective relabeling.

## Frozen test

- Source: ADMA's April 28, 2025 FDA production-process approval announcement,
  [SEC Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1368514/000114036125015881/ef20048038_ex99-1.htm).
- Request: `2d9222f9ff2edf76b1cc161bf65157f37a2e7d730e5fb81260200cf892a97bad`.
- Versions: `1.21.0-automated-research` / `governed-research-v22`.
- Runtime local commit: `eea8e005a4848764e1442cc8dd39d657112b0347`;
  published equivalent: `c1ffacd45bd1b9db1de033eb3e797176a0704243`;
  matching tree: `c67b55b886071fc80b021879fca0ee4ff95519b1`.
- Complete 142,588-byte request; unchanged 250,000-byte input ceiling and
  12,000-token output limit. No source truncation, repair, retry or second call.
- All three living-master revision IDs matched the frozen complete texts before
  dispatch. Prior answers, reviewer judgments and frozen reference were excluded
  from the provider request.
- Returned model: `gpt-5.5-2026-04-23`; completed with 30,428 input tokens,
  zero cached input tokens and 7,826 output tokens (including 3,284 reasoning).
- Cost: **$0.38692**, calculated from reported usage and the freshly verified
  [GPT-5.5 rates](https://developers.openai.com/api/docs/models/gpt-5.5).
  The fixed campaign ceiling was $1.75; conservative planned allowance $1.17294.

Provider summary digest:
`1c31e92c5730e62c15d33ed8d3ccb4e8e0fc7ba96f27c1089e60721bb2ea2524`.
Original response envelope digest:
`56c4a0db94aa5b1336f749398b915e58acabe1a3565de05e5855f8a77d648317`.
Original full draft digest:
`c058e5582fb3793d99349eb9c60974a4e5ac3712bda3b2e93e3e3263a968be71`.
Field report digest:
`0743492fb3e53b666689226ef92d24c63a0a3238902d23b921e2e46c050b5478`.

## Source review

The separate AI reviewer reused its frozen source-first reference. It had
previously seen and reviewed v21, so this v22 review is **not blind**. Shared-model
limitations remain; it is not independent human acceptance. Assessment records
bind each judgment to the exact original field value and substantive source.

The core regulatory event, approximately 20% same-plasma yield comparison,
named product beneficiaries and qualified future economic benefits are retained.
The absolute-baseline explanation now correctly acknowledges the disclosed
comparison basis. The previous materiality-summary forecast mix is separated.

The forecast term nevertheless records attribution to FDA approval as conditions.
Its condition explanation repeats this interpretation, and both condition
clauses use `EVENT_OCCURRENCE` for attribution of forecast effects. The source
supports the causal account; that does not make it a disclosed operational
condition or establish that forecast benefits occurred. These fields require
revision under the v22 contract.

A broader review also flags the demonstrated-yield context note labeled
`EXPECTATIONS`, despite the corresponding economic term correctly using
`REPORTED_RESULT`. The focused field recorder does not replace review of such
categories or overall source meaning.

The focused assessment covers **all 47 field items**: four overlapping revision
items identify the forecast condition facet, its explanation and its two temporal
clauses. These counts describe review coverage, not an accuracy rate. The review
status is `REVISIONS_REQUIRED`; the original research admission is not upgraded.

The broader assessment covers all 26 other checklist items and all 14 frozen
source anchors. It also retains two wording/category ambiguities: generic
forward-looking caution labeled `COUNTEREVIDENCE` must not be read as observed
adverse results, and an optional extra-document follow-up must not imply that
the governing catalyst-verification requirement is optional. No material
economic omission was identified within the selected source scope.

Exact binding verification checked 84 original draft values and 271 source
quotations. Review verification manifest:
`2a1fa55dea1ec67d46859434892614281714cdf517b878e6b66dd915a3aa42b8`.

## Verification and boundaries

The implementation's prior **1,026 passing tests**, including 22 new regressions,
remain applicable: all 100 tested Python source hashes were verified unchanged.
This step changes evidence documentation only; it does not claim a new suite run.

All **121 outcomes replay exactly: 59 research admissions / 62 rejections**.
The previous 120 outcomes remain 58 admissions / 62 rejections, and all prior
ledger and artifact hashes match. The 25 ledgers include the single new attempt.
Read-only replay manifest:
`80029629148b0a10481e6922c543547583f667e3db329557323fd04bb7b796fb`.

The test is `INFRASTRUCTURE_EVALUATION`; its source packet remains
`INFRASTRUCTURE_TEST`. Every result is `eligible_for_handoff=false` and semantic
acceptance remains `NOT_ESTABLISHED`. Original admission is unchanged. No
production, Journal, strategy-methodology, execution, merge or deployment changes
were made. Phase 1 SHADOW and broker-disabled repository boundaries remain.
**Live runtime configuration and live Journal state were not verified.**

The next work should address the remaining field distinctions offline and test
them against the complete preserved counterexample. Another paid call is not
part of this test. One targeted output does not establish broader reliability,
strategy expectancy or profitability.
