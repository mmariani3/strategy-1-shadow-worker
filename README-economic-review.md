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

The offline implementation step made no paid calls. The subsequent four-call
comparison below evaluated the unchanged runtime.

## September 22, 2026 comparison

**Neither model is accepted for unattended qualification.** Both GPT-5.5 drafts
passed structural admission but omitted source economics. Both Mini drafts failed
the existing event-scope check and also had substantive source/prose problems.
All four received `REVISIONS_REQUIRED` in the separate implementation-author review.
That review records judgments; it does not repair or replace original model results.

### Design and provenance

- Two previously undispatched exact document bodies: a DAIC/CID acquisition-term-sheet
  [8-K](https://www.sec.gov/Archives/edgar/data/2033770/000121390026100595/ea0305699-8k_cidhold.htm)
  and an FSI [earnings-call transcript](https://www.benzinga.com/news/26/09/61866058/flexible-solutions-intl-q2-2026-earnings-call-complete-transcript).
  Neither exact body nor substantive source ID appeared in the prior 97 dispatches.
- Same discovery collection as prior tests. The implementation author read the
  captured texts and froze 25 scope-conditional source anchors before new responses.
  This is **not independent acceptance**, and captured-document completeness and
  availability at the original scan remain unestablished.
- Full masters, source/context, 12,000 output tokens, 250,000-byte input ceiling,
  selected models and request schema were retained. Request bodies were approximately
  205 KB and 230 KB. Oversized alternatives were retained in the inventory without
  truncation; no response failures were discarded or retried.
- Four actual CLI calls, four completed provider responses, zero retries. Runtime
  local commit `197f1ca50413e54af37e6262dcfd08fcf5d9f2f6`, GitHub
  `7e6631e20b6ed390e97ac69073f9b14bc4945826`, matching tree
  `2a3e8b29c20792f88c4ad6a0bbfedcf7d153ed6e`; no mid-campaign code changes.
- New observations are `INFRASTRUCTURE_EVALUATION`, ineligible for handoff. Original
  source-run identity remains preserved; no new candidate/signal/trade IDs are
  manufactured for historical research.

| Source | Model | Original technical outcome | Usage-priced cost |
| --- | --- | --- | ---: |
| DAIC | gpt-5-mini | Rejected: `CLAUSE_EVENT_SCOPE_MISMATCH` | $0.033590 |
| DAIC | gpt-5.5 | Research draft admitted; semantically unverified | $0.468660 |
| FSI | gpt-5-mini | Rejected: `CLAUSE_EVENT_SCOPE_MISMATCH` | $0.034302 |
| FSI | gpt-5.5 | Research draft admitted; semantically unverified | $0.479660 |

**Total: $1.016212.** Token usage was priced using the verified official
[Mini](https://developers.openai.com/api/docs/models/gpt-5-mini) and
[GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5) rates, including
cached-input distinctions. Preflight billing showed $6.83 with auto-reload off;
the full-batch conservative allowance was $3.1507645. After the run, billing still
displayed $6.80, which had not reflected all completed usage. Conservative remaining
credit is **about $5.80**, assuming no unrelated spend. No billing setting changed.

### Source/prose findings

| Finding | Original evidence and assessment | Disposition / limit |
| --- | --- | --- |
| Acquisition obligations still omitted | Both DAIC drafts omit up-to-$150k fiduciary-out reimbursement and roughly $700k postclose lease backstop with 30-day letter-of-credit timing. GPT-5.5 cites the source and names the categories but omits the actual economics. | Revision required; prompt v15 has not solved completeness. |
| Consideration and funded costs compressed | Both omit preferred-value/blocker/liquidation details and $6 additional-share pricing/$500k Envoy funding limit. Ambiguous source wording about 400,000 preferred shares is not resolved by guessing. | Preserve source qualification in any future extraction. |
| Scope determines what is required | Mini expressly includes note and settlement economics but omits guaranteed interest, cap conditions, default costs and settlement fee breakdown. GPT-5.5 declares acquisition-only scope; full note/settlement completeness is left unassessed, not counted as an automatic omission. | Different scopes prevent a common accuracy denominator. |
| Approval conditions | GPT-5.5 retains that shareholder approval is not a closing condition. Mini omits that distinction and demands completed closing/conversions and full exhibits as prerequisites for prospective announcement materiality. | Stronger-model distinction preserved; Mini prerequisites unsupported. |
| Earnings economics | GPT-5.5 preserves sales decline, loss/EPS, prior-year irregular revenue and forecast-versus-result distinctions, but omits $6.5M/year/five-year contract terms and up-to-$3M conditional R&D amount/horizon. Mini omits reported losses and much of the economic context. | Both require revision. No measured earnings surprise is invented or approved. |
| Cost counterevidence | GPT-5.5 retains lower margins and generic cost pressures but omits the stated tariff range and conditional price-increase response. Mini retains little concrete downside context. | Revision required for the declared outlook scope. |
| Event/publication timing | Mini infers the FSI call occurred around September 18 from article publication despite conflicting Monday/August clues. GPT-5.5 keeps call timing unresolved and preserves the August filing reference. Its DAIC support also tags an earliest-event report date as `PUBLICATION`, despite correct prose date separation. | Timing semantics remain a review responsibility. |
| Source requirements and tier fit | Mini treats official documents as universally required and proposes a catchall Tier B corporate-action mapping. GPT-5.5 makes official-source followup optional and leaves FSI tier unresolved, distinguishing 2025 contracts from the September transcript. | No new source/category rule or tier approval. |

The author inspected original findings **and support-clause prose**, then recorded
50 anchor/answer decisions and 16 aspect assessments. Optional or outside-scope
details remain explicitly unresolved. These are finite source-reference judgments,
not a complete source inventory, numerical strategy thresholds, or independent review.

| Draft | Fully selected anchor spans | Partly selected | Not selected |
| --- | ---: | ---: | ---: |
| DAIC / Mini | 0 | 9 | 4 |
| DAIC / GPT-5.5 | 13 | 0 | 0 |
| FSI / Mini | 1 | 3 | 8 |
| FSI / GPT-5.5 | 8 | 2 | 2 |

All selections resolve to existing locations, with no duplicate selections inside
individual clauses. **Location coverage is not semantic completeness**: GPT-5.5
selected every DAIC anchor span while omitting key amounts from its prose.

### Integrity and next boundary

- All **97 prior outcomes** remain unchanged. Including this campaign, all **101**
  replay exactly: **45 research admissions and 56 rejections**, across 17 unchanged
  ledger hashes during verification. Original four responses and failures retained.
- Four new location audits and four attributed completeness reviews reproduce exactly
  from original drafts. Additional findings bind to exact original draft paths/digests.
- Existing **748-test** v15 suite passed before this campaign. Runtime did not change;
  this step adds evidence/documentation, not a new code version or new test-count claim.
- Frozen plan SHA-256:
  `76f15c84b4b8ef24e566993c87f32857d4a996a37f45543d091a4bce8f64ea04`.
  Private final-verification ID:
  `fd40afc337f5e93401c6f649af6489b3715605d6a94e5d18a5f27dc9aa7ac51e`.

No old-prompt calls were made on these two documents, so this comparison cannot
establish that v15 caused an improvement. Two documents cannot establish general
model reliability, positive trading expectancy or unattended readiness.

Next engineering step: design an explicit source-bound economic-term inventory
that preserves amounts, conditions and timing before generating the short summary,
and checks that included terms survive summarization. Use saved responses for free
regressions first. Detecting every material omission still requires source assessment;
numeric extraction or another prompt alone is not proof of completeness. Version any
future contract/prompt change separately, keep old failures, and budget any new paid
comparison only after offline checks. No further paid calls are scheduled.

No schema migration, merge, production deployment, Journal write or execution
enablement occurred. Strategy v0.3, Experiment v0.5 and Automation v0.4 remain
unchanged. Phase 1 SHADOW and disabled execution remain repository boundaries.
**Live trading-service configuration and live Journal state were not reverified.**

OpenAI notes that [structured outputs can still contain mistakes](https://developers.openai.com/api/docs/guides/structured-outputs#handling-mistakes).
This change applies instruction-level corrections while retaining separate source
review; it does not treat schema compliance as semantic validation.
