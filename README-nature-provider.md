# v24 bounded provider test

## Result

**Rejected: `NATURE_SOURCE_BINDING_MISMATCH`.** The provider returned a completed
answer, but two core classification declarations did not repeat the exact source
sets of their corresponding assertions. No research admission, retry, repair,
completed field report or trading handoff was created.

The original complete response is retained. A separate raw-answer source review
is recorded without changing its rejected admission.

## Execution and cost

| Field | Value |
| --- | --- |
| Source | [Complete ADMA April 28, 2025 release](https://www.sec.gov/Archives/edgar/data/1368514/000114036125015881/ef20048038_ex99-1.htm) |
| Requested / returned model | `gpt-5.5` / `gpt-5.5-2026-04-23` |
| Implementation / prompt | `1.23.0-automated-research` / `governed-research-v24` |
| Runtime local commit | `d362d21aea3b1e10c439d403475b11129184f0a2` |
| Runtime tree | `57df9ca69921c917ea97bc9a7bd3b7dd4b2e5171` |
| Request | `ef106bb33f1256a0bae7bc3a595e29f251d24174d3a7d265a8450a9f3e690e20` |
| Input body / ceiling | 151,136 bytes / 250,000 bytes, unchanged |
| Output ceiling | 12,000 tokens, unchanged |
| Usage | 32,020 input, zero cached; 8,736 output, including 4,038 reasoning |
| Calls / retries / repairs | 1 / 0 / 0 |
| Token-derived cost | **$0.42218** |
| Original envelope digest | `a897cb1d7b2b2dcc3e2cc63f7c2c06f9ecb172027be0d70bab28b615317dbcbf` |
| Rejected review package | `aec32f10bc4c88e515d4af3b2e0d710a22116cc0fde24e83ad41a4335750409c` |

The cost uses the current [GPT-5.5 rates](https://developers.openai.com/api/docs/models/gpt-5.5)
of $5 / $0.50 / $30 per million input / cached-input / output tokens. It is derived
from returned usage, not a settled invoice. The billing page displayed $10.32
before the call, with auto-reload off. A conservative estimate after this call
is $9.88782, assuming no other spending. Billing settings were not changed.

The source, pre-v21 reference and full governing-master texts were preserved.
Current master revisions were checked again before dispatch. Previous answers,
review judgments and synthetic examples were not model inputs. No truncation or
reduced limit was used. This establishes that the API accepted the schema and
completed this request within its output budget; host validation still rejected it.

## Binding diagnosis

| Zero-based term | Declaration citations | Corresponding assertion citations |
| --- | --- | --- |
| 1: forecast output/product benefits | 8, 12, 13 | 8, 12, 13, 53-68 |
| 2: forecast financial effects | 8, 21, 22 | 8, 21, 22, 53-68 |

The missing declaration numbers refer to the source's cautionary passages.
Those passages and their qualifications are still present in the original
assertions and forecast terms. This is an exact-binding defect, not a claim that
the source evidence or all caution text vanished.

## Source review

The separate AI reviewer re-read the complete source, all three masters and its
unchanged pre-v21 source reference before reading this answer. Prior v21-v23
exposure is disclosed: this is a targeted non-blind repeat with shared-model
limitations, not independent human acceptance or an unseen-source benchmark.

In this answer, demonstrated yield is separated from forecast production/product
benefits and forecast financial effects. Forward-looking cautions are retained
locally in both forecast terms. These are case-specific observations, not a
general improvement rate, and they do not override the host rejection.

The reviewer also identifies a separate temporal-label defect:
`draft.research.materiality_coverage.support.clauses[1]` expressly describes a
forecast beginning in late 2025 and continuing into 2026 and beyond, but labels
itself `NOT_TEMPORAL`. Correct forecast fields elsewhere do not cure this local
label. This remains distinct from the two exact citation-binding mismatches.

The review covers all 58 field items (55 supported, three revisions), 15 broader
findings (12 supported, three overlapping revisions) and all 14 frozen source
anchors (13 supported, one overlapping timing revision). These are descriptive
coverage counts, not accuracy or acceptance scores. The three defects comprise
two declaration-binding mismatches and one semantic timing-label conflict.

Read-back verification checked 151 exact original-answer bindings, 629 exact
source quotations and 19 named-master quotations. The original ledger remains
rejected, with no completed assessment. Review verification:
`e6c661a555730bfee4c84b95f8be8f94878d487ae5d1009749357091c4fb2094`.

## Preservation and validation

All **123 outcomes replay exactly: 60 research admissions / 63 rejections**,
across 27 ledgers. The prior 122 outcomes, 26 ledgers and all preserved source,
response and judgment hashes are unchanged. The prior v23 complete report and
attributed assessment still reproduce exactly.

Replay manifest: `b765a47285b55fecf67d4017beddbe753de29b4cf85f9447cc1a38539870604a`.
The implementation passed **1,078 tests**, including 24 new regressions. All 104
tested Python files retain their tested hashes. Subsequent changes are report
documentation only; no second full-suite run is claimed.

The standard field-assessment recorder requires a completed research response.
It was not used for this rejected answer. The raw-review package instead labels
its rejection explicitly and preserves the original envelope, response text,
wrapper, source catalog and inspection checklist. Review findings cannot upgrade
the original admission or establish semantic acceptance.

## Next step and boundaries

Next: refine the redundant citation-binding representation and the forecast
summary's temporal handling offline, retaining the full source and this rejected
answer as regression evidence. A further paid test needs a separately bounded
plan. This test does not establish hands-off readiness or profitability.

This is infrastructure evaluation, excluded from Strategy #1 evidence, with
`eligible_for_handoff=false`, `semantic_acceptance=NOT_ESTABLISHED`. No strategy,
experiment, risk, setup, trigger, stop, target or eligibility change. No Journal
write, synced-source edit, production configuration change, merge, deployment or
execution enablement. Phase 1 SHADOW and disabled broker execution remain
repository boundaries. Live runtime and live Journal state were not verified.
