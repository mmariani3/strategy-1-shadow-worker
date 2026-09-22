# Research extraction v15

The default prepare-only CLI now uses `1.14.0-automated-research` /
`governed-research-v15`. This is a prompt revision to address the source/prose
failures recorded in the [completeness review](README-completeness-review.md).
The output schema, model selection, source catalog and admission gates are unchanged.

## Changes and limits

| Finding | Instruction change | Remaining limit |
| --- | --- | --- |
| Financing summaries omitted an earned, noncontingent fee | Inspect scope-relevant fees, principal, proceeds, discounts, interest and obligations separately; preserve disclosed amount, timing and contingencies | The model may still omit facts; software does not infer economic completeness. |
| Generic conditionality hid conversion restrictions | Preserve joint conditions, future eligibility dates, elections and restrictions in the actual prose | A valid citation does not prove that the model preserved a condition's meaning. |
| Dilution/context was weakened or lost | Preserve source degree, attribution, warnings and contrary evidence | Context is not an automatic rejection or trading rule. |
| Missing private tier labels or primary documents became prerequisites | Separate source facts, missing economic facts, interpretation uncertainty and optional document followups | Unclear tier mapping remains unresolved and unapproved. |
| Sales evidence was mapped to the nearest earnings category | Require substantive fit to the actual master; keep reported metric and magnitude distinct | No category change or quantitative surprise threshold is introduced. |
| Citation locations were treated as completeness | Explicit final source/prose inspection of economics, conditions, timing and counterevidence | Independent semantic acceptance remains unestablished. |

The instructions are general and contain no ABTS/CVI identifiers, amounts or answer
keys. They do not require every event to disclose financing terms or turn source
silence into proof of absence. Full governing masters, source text and context remain
available. The model still returns the existing inline-support structure; it is not
asked for private reasoning or additional unsupported approval fields.

## Version and evidence integrity

`research_economic.py` binds the entire new prompt, full masters, source message,
schema and request digest before reserving a model call. It passes new responses
unchanged through the frozen v14 parser. An internal parser context is derived from
the new request; it is not a replacement provider request or a historical replay.

The outer result identifies v15, while support-parser attribution remains v14
because that implementation actually performs the checks. The result records both
versions and the actual v15 catalog/request identity. Compliance and semantic
completeness remain `NOT_ESTABLISHED`; handoff remains disabled.

The reference-location audit accepts v15 with a distinct `1.1.0` audit version.
Its v14 path retains the exact historical `1.0.0` output. The attributed completeness
review can inspect either. Neither sidecar changes model admission or repairs a
saved answer. Historical responses are never relabeled as v15.

## Offline verification

- **748 tests passed**, including **18 new v15 regressions**.
- Tampered prompt/master/source/schema/version/digest/packet, enabled tools or
  storage stop before dispatch reservation.
- Full source, schema, model and output allowance remain unchanged; oversized
  requests fail without truncation. Durable recovery does not repeat a saved call.
- Automatic tier approval, wrong timing, missing source support and invalid
  selections still fail. Deliberately omitted facts and false prose cannot establish
  semantic completeness even when a synthetic response passes structural admission.
- All **97 saved provider outcomes** replay unchanged: 43 research admissions and
  54 rejections. Sixteen original ledger hashes remain unchanged.
- All four saved v14 location audits and four author completeness reviews reproduce
  exactly. Four v15 requests were prepared from the reused development packets only;
  no old provider answer was reassessed as a new v15 response.

Those preparation checks retain 12,000 output tokens and a 250,000-byte input
ceiling. ABTS bodies are about 162 KB; CVI bodies about 158 KB. The added instructions
increase each body by 4,859 bytes. Bytes are not tokens or a dollar spending limit.

**No v15 model calls have been made.** Offline tests establish protocol behavior,
not improved model accuracy, completeness, strategy edge or unattended readiness.
No schema migration, production deployment, journal write or execution enablement
is part of this change. Strategy v0.3 and Experiment v0.5 remain unchanged; Phase 1
remains SHADOW. Live trading-service configuration was not reverified.

## Next comparison

Before dispatch, freeze new source documents and attributable source-backed
references without seeing the new model outputs. Keep the selected Mini and
GPT-5.5 models, full evidence and the existing allowances. Check actual request sizes,
current model availability/prices and sufficient API funding for the entire batch.
Record the reference author's exposure and independence limits; new documents alone
do not make an author assessment independent.

Compare technical admission separately from economic fact/condition preservation,
missing material terms, unsupported prerequisites, timing and tier interpretation.
Retain every response and failure; no response repair, automatic retry, selective
discard or retrospective trade observation. A later prompt change needs another
version and must not redefine the frozen comparison halfway through.

Current engineering verification used no paid API calls. The last live billing read
showed $1.83 and auto-reload off, below the prior comparable four-call allowance of
$2.50. This is a funding checkpoint, not a price guarantee for documents not yet
selected. Do not shrink the comparison to fit a low balance.

OpenAI notes that [structured outputs can still contain mistakes](https://developers.openai.com/api/docs/guides/structured-outputs#handling-mistakes).
This change applies instruction-level corrections while retaining separate source
review; it does not treat schema compliance as semantic validation.
