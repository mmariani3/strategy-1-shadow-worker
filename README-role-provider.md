# v23 preserved-source provider test

## Result

One GPT-5.5 request on the complete preserved ADMA source returned a research
draft. The response passed v23 structural validation. Source review is recorded
separately; neither result authorizes a trade or establishes general reliability.

## Reproducible execution record

| Field | Value |
| --- | --- |
| Source | [ADMA April 28, 2025 company release, SEC exhibit](https://www.sec.gov/Archives/edgar/data/1368514/000114036125015881/ef20048038_ex99-1.htm) |
| Requested / returned model | `gpt-5.5` / `gpt-5.5-2026-04-23` |
| Implementation / prompt | `1.22.0-automated-research` / `governed-research-v23` |
| Runtime local commit | `5ce21239fe42db3c0ca7403fd30da93d0e33cd2d` |
| Runtime GitHub commit | `3f830ad937c33b16ec7fbec256808a84878de7dc` |
| Matching runtime tree | `0e41fd267253b40b7c68e9ddb82692158591a9b8` |
| Exact request | `a3f12246b12aeceeb1bd36c1baecdd56614f81f9dd8c10e159bbb11fa39bcbe2` |
| Packet | `a2faa8e92c6bd756e29ea7370178b5ea97170ae1f85ec8011856e0720d2074d2` |
| Serialized request | 147,846 bytes; unchanged 250,000-byte input ceiling |
| Output ceiling | 12,000 tokens, unchanged |
| Usage | 31,439 input tokens, zero cached; 7,321 output, including 3,106 reasoning |
| Calls / retries / repairs | 1 / 0 / 0 |
| Token-derived cost | **$0.376825** |
| Preserved response digest | `05378bdeeb5099ec9da427827682ad893009ee049d84a127c38008a6984e74b9` |
| Original review report | `65f2cd20c0649d4f497262cbae24168bf36b275ebc2868496caef5dee2852c46` |

Cost uses the freshly checked [GPT-5.5 rates](https://developers.openai.com/api/docs/models/gpt-5.5):
$5 / $0.50 / $30 per million input / cached-input / output tokens. It is computed
from returned usage, not a settled invoice. The billing page still displayed
$10.70 after the call; allowing for display rounding and this request gives a
conservative estimated balance of $10.313175, assuming no other spending.
Auto-reload was off and billing settings were not changed.

The request retained the full source, all governing-master texts and the same
pre-v21 frozen source reference. Prior answers, judgments and author-constructed
corrections were not sent to the model. Current master revision IDs matched the
stored texts before dispatch. No source truncation, reduced limit, extra model
call, repaired answer or altered historical record was used.

## Source review

The separate AI reviewer re-read the complete source, original frozen reference
and all three governing masters before reading this response. It had previously
reviewed v21/v22 answers. This is a targeted non-blind repeat with shared-model
limitations, not an unseen-source benchmark or independent human acceptance.

**Outcome: REVISIONS_REQUIRED.** In this answer, the previous false conditions,
condition timing labels, reported-result context category and caution category
are corrected. The document follow-up expressly preserves governing verification
requirements. These are observations about this single answer, not a measured
general improvement rate.

The remaining issue is local to the yield/output economic term: its
`REPORTED_RESULT` classification combines demonstrated yield with anticipated
future output/product benefits. Its qualification explanation also limits
qualifiers to comparison basis and product scope despite the release's
forward-looking caution. Demonstrated performance and expected benefits need
separate treatment, with their applicable qualifications retained.

The percentage, same-plasma comparison basis, beneficiaries, timing and wider
caution remain in the original answer. The finding does not claim these facts
were omitted, and the original response has not been repaired. Focused field
decisions and broader economic classification judgments are recorded separately.

The focused assessment records **53 decisions: 52 supported and one requiring
revision** at the mixed term's qualification facet/reason. The broader review
covers all **24 other checklist items**, including **14 frozen source anchors**,
and separately records the mixed term-level classification. Repeated findings
about that term are overlapping views, not independent failures or an accuracy
sample. All **77 checklist items** are covered.

Exact verification checks **98 original-value bindings, 254 source quotations
and four governing-master quotations**. This validates attribution and identity,
not the truth of the assessor's judgments. The original review and separate
assessment retain `semantic_acceptance=NOT_ESTABLISHED` and
`eligible_for_handoff=false`.

## Preservation and verification

All **122 outcomes replay exactly: 60 research admissions / 62 rejections**,
across 26 ledgers. The previous 121 outcomes, 25 ledgers and prior source,
response and review artifacts retain their original hashes. Admissions mean
research drafts only. New review judgments never change original admissions.

Replay manifest: `0e22db027d9b677792c8d26c62aec6eeff0740873785adcb9bd5fabf1bc050f8`.

The prior **1,054-test run** remains the code-test evidence; this follow-up only
changes this report and `README-role-review.md`. All 102 tested Python source
hashes are checked against that run. No new full-suite run is claimed.

Private artifacts retain the exact request, provider envelope, original text,
parsed wrapper, read-only ledger, complete source-bound review and attributed
judgments. The HTML export is escaped and deterministically reproducible;
mobile/visual usability is not asserted.

## Boundaries and next step

This is `INFRASTRUCTURE_EVALUATION`, excluded from Strategy #1 evidence, with
`eligible_for_handoff=false` and `semantic_acceptance=NOT_ESTABLISHED`.
No methodology, risk, setup, trigger, stop, target or observation-eligibility
changes. No Journal writes, synced-source edits, production configuration changes,
merge, deployment or execution enablement. Phase 1 SHADOW and disabled broker
execution remain repository boundaries; live runtime and Journal state were not
verified in this test.

Next: use this preserved answer to address mixed reported-result/forecast terms
offline, with regression coverage that preserves both meanings and their
qualifications. A later provider test needs its own bounded plan. This run does
not establish hands-off research readiness or strategy profitability.
