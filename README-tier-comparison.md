# v19 provider comparison — September 22, 2026 Pacific

**Both models accepted the new schema and produced technically valid research
drafts. Both still need source-content revisions in the implementation author's
review.** Matching a rule's tier label does not establish that the rule applies.

## Frozen test

The complete [January 6, 2025 Fubo/Disney announcement](https://www.sec.gov/Archives/edgar/data/1484769/000149315225000390/ex99-1.htm)
was captured for the first time in this evaluation corpus. Its extracted document
body was checked against all 113 earlier dispatched outcomes for exact overlap.
Eight source anchors were fixed before either answer; they cover the combination,
ownership, distribution, governance/projections, settlement/loan, termination fee,
publication/event timing and risk qualifications. Anchor relevance follows each
answer's stated scope; optional operational context is not automatically a defect.

A second complete [KDP/JDE Peet's announcement](https://www.sec.gov/Archives/edgar/data/1418135/000095014225002257/eh250670939_ex9901.htm)
was also captured with eight frozen anchors. Both model preparations hit
`INPUT_LIMIT_EXCEEDED_NO_TRUNCATION`. That case remains recorded as blocked; the
document was neither shortened nor substituted. No KDP model request was sent.

The Fubo input was approximately 176 KB for each model. The 250,000-byte ceiling,
12,000-output-token limit, full sources, masters, prompt and parser remained fixed.
One request per model, no paid retry or response repair. The conservative allowance
was $1.40889325 against $2.82529075 estimated credits ($2.84 displayed before calls).

Infrastructure fixtures retain `INFRASTRUCTURE_TEST`, synthetic run IDs and null
candidate/signal/journal-trade IDs. The normal discovery CLI excludes them. The
isolated harness uses the same request validator, durable attempt ledger, transport
and parser. Session/phase fields are schema placeholders. These historical releases
are not current catalysts, prospective trade evidence or production discovery runs.

## Original results

| Case | Model | Technical outcome | Author source review | API cost |
| --- | --- | --- | --- | ---: |
| FUBO | GPT-5 mini | Research draft retained | Revisions required | $0.02964000 |
| FUBO | GPT-5.5 | Research draft retained | Revisions required | $0.42412000 |
| KDP | Both planned models | Blocked before dispatch: full input too large | No model answer | $0 |
| **Total** | **2 calls** | **2 research admissions** | **No independent acceptance** | **$0.45376000** |

Costs use returned token usage, cached-token discounts and the official
[Mini](https://developers.openai.com/api/docs/models/gpt-5-mini) and
[GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5) rates checked before
dispatch. The post-call UI displayed $2.81 with auto-reload off, apparently still
awaiting the stronger-model charge. The conservative usage-based balance is
**$2.37153075**, excluding unrelated account usage. No billing settings changed.

### Rule matching

Both proposals contain only Tier A catalog rows, so the new structural constraint
worked on this pair. Mini selected every A row, 72–77, including earnings/guidance
surprise, regulatory decision and industry shock. The captured announcement does
not establish those events. This exposes a remaining substantive mapping failure
inside the allowed tier. GPT-5.5 selected acquisition and financially significant
strategic announcement, 75/76, which plausibly fit the disclosed combination as a
research proposal. Neither proposal constitutes catalyst approval.

### Source meaning and completeness

**Mini:** principal amounts and contingent termination-fee direction are retained.
Its loan timing entry says the commitment occurs in 2026, whereas the source says
Disney has already committed to provide the loan in 2026. The conditions rationale
also infers a likely closing condition for that loan without loan-specific source
support. Publication timing is marked evidenced but discusses filings, links and
the investor call instead of establishing when publication occurred. Some payment
entries cite a sentence continuation without the payer/at-signing clause, although
that clause survives elsewhere in the inventory. Regulatory-risk selection stops
before the consequence that approval conditions could harm benefits or cause
abandonment; further disclosed tax/litigation/contract-consent risks are omitted.

**GPT-5.5:** preserves the separate settlement, loan and conditional fee, distinguishes
funding year from commitment, leaves missing payment deadlines unresolved, and
separates announcement date from unknown clock time. It retains the cash-flow
projection as a forecast. Its stated scope includes risk qualifications, but the
summary omits disclosed tax-treatment, new transaction-litigation and third-party
contract-consent risks. A selected passage ends in the middle of the tax-risk
condition without the continuation. Generic caution and future document followups
do not preserve those already-disclosed qualifications.

These are explicit implementation-author judgments with access to both source and
answers, not independent adjudication. Optional operational details remain marked
optional/unresolved. No citation-coverage percentage or defect count decides
materiality. Followups for agreement/loan mechanics remain research questions;
they do not create new strategy prerequisites.

## Verification and evidence integrity

The unchanged runtime previously passed **876 tests**. No code changed for this
comparison, so the full suite was not rerun for the documentation update.

- All **115 outcomes** replay exactly: **54 research admissions / 61 rejections**.
  All 113 earlier outcomes and all 20 earlier ledger hashes remain unchanged.
- Both new request reservations and original provider responses are retained;
  two source-location audits, attributed reviews and omission reports regenerate
  exactly. Both remain ineligible for trading handoff.
- Exact economic summaries retain five Mini terms and six GPT-5.5 terms, including
  their full selected source wording.
- Two immutable HTML review pages regenerate exactly. Each retains 250 passages
  and complete substantive source text; no indexing gaps were found. Their queues
  contain 235/204 location flags grouped into 29/17 navigation groups. These include
  optional text and boilerplate and are **not counts of material defects**.
- The transient first replay attempt detected the still-changing new ledger while
  the stronger-model call was active and stopped. After the writer closed, the
  complete read-only replay passed. No model call was repeated.

Tested runtime: local `2a3f4d50c8965b889c5858bf91b0fba2bbe87b89`, GitHub
`c494cc15a8c35ad87f94274b52086c25086a9435`, matching tree
`bd4aa71499e84e1ef3c9015c0b7c2dab4a2b367f`.
Verification: `b23a1fe135d70978ec265c802d5f3705e86b2965d2bc6bc047cb0539537999eb`.
Private `tier-comparison-20260922` artifacts retain the frozen plan, complete
captures, requests, source references, original responses, reviews, pages and hashes.
Raw sources and private masters are not published in this PR.

## Remaining work and limits

This pair establishes provider acceptance and structural compliance on **one**
new-to-corpus historical source. KDP's blocked case limits coverage. Convenience
selection, possible training familiarity and author review prevent independent,
representative accuracy or profitability claims. No model is approved for
unattended qualification.

Next work should be offline: make individual rule-to-fact support reviewable,
address timing assertions and unsupported conditions, and improve review of
source continuations. KDP's full-input failure needs an explicit design decision;
do not silently truncate it or raise limits as part of a comparison. No further
paid call or runtime fix is included in this results update.

Living Strategy v0.3, Experiment v0.5 and Automation v0.4 revisions were reread
and matched complete stored masters. No methodology, risk limits, observation
eligibility, synced sources, Journal, deployment or broker changes. Phase 1 SHADOW
and broker execution disabled remain repository boundaries. Live runtime
configuration, production dispatch and Journal state were not checked here.
