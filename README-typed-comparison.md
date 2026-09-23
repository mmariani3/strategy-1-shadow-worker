# v18 provider comparison — September 22, 2026 Pacific

**All four answers satisfied the new topic-role/event-support shape. Three passed
the complete technical parser; all four still need content revisions within the
implementation author's source checklist.** This is evidence of a working schema,
not independent semantic acceptance or readiness for unattended qualification.

## Frozen evaluation

Two historical SEC exhibits were newly captured and checked for exact document-body
overlap against all 109 prior outcomes:

- [Verona shareholder approval update, September 24, 2025](https://www.sec.gov/Archives/edgar/data/1657312/000110465925092968/tm2526799d1_ex99-1.htm).
- [BioNTech/BMS collaboration, June 2, 2025](https://www.sec.gov/Archives/edgar/data/1776985/000177698525000039/a991250602_bntxxbmsxprxcol.htm).

Both complete documents went to GPT-5 mini and GPT-5.5, one call each per source.
Sixteen source anchors were fixed before responses. No runtime, prompt, reference,
input limit or model changed during the run. No truncation, answer repair, model
substitution or paid retry occurred. The 250,000-byte input and 12,000-output-token
limits stayed unchanged; request bodies were approximately 155 KB and 161 KB.

The fixtures retain `INFRASTRUCTURE_TEST`, synthetic run IDs and null candidate,
signal and journal-trade IDs. The normal CLI excludes them. The isolated harness
uses the same request validator, durable ledger, provider transport and parser;
it does not establish production discovery dispatch. Session/phase fields are
schema placeholders. These historical documents are not current trading catalysts.

The implementation author reviewed source/prose, with exposure to prior results.
The sources are two related-sector convenience cases, not representative samples.
Models may know them from training. New-to-corpus does not mean independent evidence.

## Original results

| Case | Model | Technical result | Author source review | API cost |
| --- | --- | --- | --- | ---: |
| VRNA | GPT-5 mini | Research draft retained | Revisions required | $0.02681750 |
| VRNA | GPT-5.5 | Rejected: `TIER_RULE_MAPPING_REQUIRED` | Revisions required | $0.39012000 |
| BNTX | GPT-5 mini | Research draft retained | Revisions required | $0.02887875 |
| BNTX | GPT-5.5 | Research draft retained | Revisions required | $0.42051500 |
| **Total** | **4 calls** | **3 admissions / 1 rejection** | **No independent acceptance** | **$0.86633125** |

Admission only permits retention as research. It does not establish factual
correctness, catalyst approval, observation eligibility, setup validity or a trade.

### Specific findings

**VRNA / Mini:** abbreviated voting prose loses the majority-in-number limb and
precise denominators. The economic timetable omits record-time, suspension and
settlement details. Payment-date citations omit adjoining recipient labels; risk
selection stops before the litigation-cost continuation. Some future dates remain
inside publication-labelled clauses. The model also requests completed closing
evidence for a scope describing an earlier approval announcement.

**VRNA / GPT-5.5:** preserves substantially more voting, payment and conditional
timetable detail. It omits CREST entitlement disablement within its chosen timetable
scope. Its tier proposal includes rule 71, general catalyst guidance with no tier,
alongside acquisition rule 75. The existing parser requires every proposed-tier
reference to match that tier and rejects the original answer. No mapping was fixed.

**BNTX / Mini:** preserves the main payment amounts and sharing exceptions, but
omits both parties' independent-development rights and specific collaboration
downside. Some clinical claims cite general program text instead of the precise
phase/timing passages; a reported-result term mixes existing exposure with plans.

**BNTX / GPT-5.5:** separates payment categories, development rights, sharing
exceptions and existing versus planned trials more clearly. BMS risk language is
retained in narrative context, not the economic inventory. The author flags omitted
collaborator-continuation and related economic risks as relevant to the selected
partnership scope. This is an attributed scope judgment, not a new strategy rule
requiring every boilerplate sentence or a software-proven material omission.

## Verification and limitations

| Check | Verified result | Limit |
| --- | --- | --- |
| Actual v18 provider schema | All four completed answers satisfy narrowed field shape | Four answers do not establish reliability or accuracy |
| Technical admission | Three retained; one original rule-mapping rejection | No answer repaired or promoted |
| Historical retention | 113 outcomes replay: 52 exact admissions / 61 unchanged rejections; all 19 prior ledger hashes unchanged | Includes all 109 prior outcomes plus this four-call run |
| Exact source summary | 13 inventory terms verified across three admitted outputs | Cannot recover unselected text or prove paraphrases |
| Attributed reviews | Four source-location audits and four source/prose reviews reproduce exactly | Implementation-author judgments, not independent review |
| Omission reports | Four immutable reports reproduce exactly | 73–160 flags per answer include optional context and boilerplate; not defect counts |
| Catalog gaps | Full substantive source text and unindexed spans retained; BNTX has one source field with indexing gaps | Source capture completeness itself remains unproven |
| Runtime tests | Unchanged v18 runtime previously passed 847 tests, including 34 new regressions | No full-suite rerun for this documentation-only update |

The omission queue exposes both uncited material and text selected only in narrative
support. A narrative-only flag does not mean the prose omitted the fact. Review
findings remain separate from original technical outcomes. No automatic semantic
acceptance threshold, strategy prerequisite or source repair was introduced.

Runtime: local `be1292679dc15f8c7e6c1d18103e0ceb510906cb`, GitHub equivalent
`2ce839eedda7a348cdee55c088aa2d8ab8dce609`, matching tree
`c6c2a4f40554e553abd064e26472fabec4cec8b9`.
Version: `1.17.0-automated-research` / `governed-research-v18`.
Verification: `1fa4f4afc3827cd46a7340f142b4133e04e65438d9e16e44031298c44502cbb9`.

Full captures, references, immutable requests/responses, usage, author decisions,
omission reports and hash manifests remain in the private `typed-comparison-20260922`
folder. Private masters, credentials and raw ledgers are not published in this PR.

## Cost and next step

Billing showed $3.71 before dispatch, with auto-reload off. The conservative running
estimate was $3.691622; the fixed allowance was $2.52498025. Actual cost uses returned
input/cached/output tokens at the checked official
[Mini](https://developers.openai.com/api/docs/models/gpt-5-mini) and
[GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5) rates.
The conservative remaining estimate is **$2.82529075**, excluding unrelated usage.
The post-test billing page still showed $3.71, so its display lagged this run.
No billing settings changed or credits were purchased.

Next work should be offline: inspect whether proposed-tier references can be
constrained to valid tier-bearing rules without choosing the tier for the model,
and make source-review flags easier to assess while preserving all source text and
attributed judgments. Do not automatically repair answers, invent materiality
thresholds, or treat a stronger model as a substitute for semantic validation.
No additional paid run is authorized by this report.

Only this report and links changed in the repository. The living Strategy v0.3,
Experiment v0.5 and Automation v0.4 revisions were reread and matched the complete
stored masters. No methodology, risk, eligibility, synced sources, Journal or
production changes. PR9 remains a stacked draft on PR8. Phase 1 SHADOW and disabled
broker execution remain repository boundaries; live runtime and Journal state were
not checked. Nothing deployed, merged or enabled.
