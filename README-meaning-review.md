# Review individual rules, timing and source qualifications

The v19 Fubo comparison produced structurally valid drafts with unsupported rule
references, a commitment/funding timing error, an inferred loan condition and
omitted risks. The new offline meaning review records each of those questions
against the original answer and exact source evidence. **Both original answers
still require revisions.** Original outputs and admissions are preserved. Future
prepare-only requests use v20's revised instructions with the same schema and
complete sources. Improved model accuracy is not yet established.

## Future request instructions

`research_semantics.py` introduces `1.19.0-automated-research` /
`governed-research-v20`. The instructions ask the existing tier explanation to
identify support for each chosen rule; distinguish commitment from funding and
publication from calls/filings; keep unknown conditions unresolved even in reasons;
and preserve scoped downside consequences across passage boundaries. They add no
source facts, strategy thresholds or universal materiality requirements.

The schema, endpoint, caller-selected model, complete source input and caller-set
input/output limits remain unchanged. Complete request binding is checked before
reservation. The original answer passes unchanged through the frozen v19 parser
with explicit v20 attribution. Older routes remain available. The prepare-only CLI
defaults to v20 and still requires explicit dispatch authorization.

Prompt iteration remains separate from measured model behavior, consistent with
OpenAI's guidance to maintain evaluation suites as prompts change.
[Official prompt-engineering guidance](https://developers.openai.com/api/docs/guides/prompt-engineering).

## Attributed review controls

`research_meaning_review.py` adds a separate, immutable review workflow:

- One decision for **each** selected governing rule, with its original master
  revision, text, stable rule ID and offsets. Original proposed facts are visible.
  A supported judgment must link an exact selected-event or catalyst-event fact
  to a substantive source passage. A shared tier label or generic explanation
  cannot satisfy that evidence requirement. Unknown/wrong-tier references cannot
  be marked supported. An empty rule selection remains an explicit pending item.
- Separate event-timing and publication-timing items. Every recorded economic
  term retains all four facets, their reasons, status and citations, so a condition
  inferred inside an explanatory reason remains visible. Review asks assessors to
  distinguish an existing commitment, future funding, event date, publication
  date, forecast period and an unavailable clock time.
- Every supplied source anchor gets a decision. Its full quotation remains
  visible, with scope relevance explicitly recorded. Material-omission findings
  require required-for-scope relevance. Optional context does not become a new
  strategy prerequisite. Review retains risks already present in the source even
  when an answer proposes obtaining another document.
- The HTML report displays original prose, individual rules, attributed decisions,
  selected passages and adjacent context. Neighbors are labelled as context, never
  silently added to the model's citations. Full source text and all continuations
  remain available; one adjacent passage is not presumed to complete a sentence.
- All items must be accounted for, with assessor identity/kind, review timestamp,
  limitations, exact draft-field hashes and source selections. Missing/duplicate
  decisions, unknown citations, changed evidence and unsupported links fail closed
  at **review recording**. Evidence retains run/candidate/signal/journal-trade IDs,
  including existing nulls, original implementation/prompt versions and new review
  version `1.0.1-source-meaning-review`.

`REVISIONS_REQUIRED`, `REVIEW_REQUIRED` and `ATTRIBUTED_REVIEW_RECORDED` describe
the supplied review only. None constitutes semantic acceptance, tier approval,
independent adjudication or a trading handoff. Software cannot establish whether
an assessor's semantic judgment is correct. The checklist covers selected rules,
timing facts, recorded terms and supplied anchors; it cannot discover every omitted
fact or certify every assertion in the full answer.

## Reproduce without API calls

Create the dossier, unresolved assessment template and readable report:

```text
python research_meaning_review.py --packet packet.json --request request.json \
  --draft original-draft.json --reference reference.json --output reports
```

Read the full source and answer, then fill the assessment template. Preserve its
item identities; supply exact draft paths/digests and source passage numbers for
each attributed judgment. Record it with the same command and:

```text
--assessment completed-assessment.json
```

The CLI writes content-addressed JSON and HTML with the existing immutable writer.
Repeat runs with identical inputs/assessment reproduce the same files. Preserve
original input ordering: historical source-selection reports retain traversal
order. This tool supports single-scope v17–v20 drafts, including rejected answers;
it neither re-admits nor repairs them. The review CLI has no provider, credential or writer
integration. No migration is required.

## Verification and finding checklist

**920 tests passed in 151.01 seconds**, including **44 new regressions**, using
`PYTHONPATH=.deps python -m pytest -q` (set PYTHONPATH appropriately for the shell).

| Finding | Implemented review correction | Evidence | Remaining limitation |
| --- | --- | --- | --- |
| Unrelated rules share the selected tier | v20 individual-rule instructions plus separate decisions with frozen catalog and exact event/fact/source bindings | Generic proposal support rejected; each selection retained; original Mini 72/74/77 recorded unsupported, 73 unresolved | Reviewer still decides meaning; improved provider accuracy unverified |
| Commitment/funding and publication timing confused | v20 tense/date instructions, separate timing items and complete term facets/reasons | Original Mini loan and publication findings recorded as meaning errors; altered or unrelated evidence rejected | Future model accuracy unverified; source interpretation is author review |
| Unsupported loan condition hidden in a reason | Full economic term review, including explanations | Original loan conditions reason retained and explicitly reviewed with passage 98 | Free-text assumptions require meaning review |
| Missing risk continuations despite valid citations | Full anchor quotations, adjacent context and complete source links | Both Fubo risk anchors remain revisions required; uncited text, split clauses and optional context retained | Supplied anchors are not a complete semantic inventory |
| Review could omit checks or become approval | Complete item set, strict source/draft binding, explicit attribution and no-handoff result | Missing/duplicate decisions, changed inputs, invalid paths/types/times, empty source evidence and optional asserted rules rejected; fully supplied judgments still cannot approve | Assessor independence cannot be established by software |
| Historical records could change | New versions with explicit routing; historical behavior retained | All 115 outcomes replay exactly: 54 admissions / 61 rejections; all 21 ledger hashes and prior artifact hashes unchanged; 36 original audit/review records exact | Replay verifies preservation, not new model accuracy |
| New prompt could alter schema, source inputs or attribution | Same v19 schema, verified full-request binding, v20 implementation/prompt tags | Tampered prompt/schema/master/source rejected before reservation; original output unchanged; exact byte limit and retry replay tested | Provider response compliance not yet tested |
| Saved review failed HTML replay when object keys reordered | Stable formatting in review version 1.0.1 | Saved/reloaded assessment regenerates exact HTML; two real reports verified from disk | Prototype 1.0.0 artifacts remain preserved; browser visual inspection unavailable |

**18 complete v20 requests prepared and validated, none sent**, measuring
159,864–247,669 bytes. Both KDP preparations remain blocked at the unchanged
250,000-byte ceiling. No source was shortened, substituted or sent. Two saved
meaning reviews and HTML pages regenerate exactly after disk round trips.

Changed code: `research_meaning_review.py`, `research_semantics.py`; v20 routing in
`research_reviewer.py`, `review_attempts.py`, `evidence_review.py`,
`run_research_reviewer.py`, `research_reference_coverage.py` and
`research_completeness_review.py`. Regression files:
`tests/test_research_meaning_review.py`, `tests/test_research_semantics.py` and the
explicitly pinned historical fixture in `tests/test_research_tiers.py`.
Documentation: this file and links from `README-tier-comparison.md` and
`README-tier-review.md`.

## Applying the workflow to the original Fubo answers

The implementation author recorded 21 Mini items (6 rules, 2 timing, 5 terms,
8 source anchors) and 18 GPT-5.5 items (2 rules, 2 timing, 6 terms, 8 anchors).
Both reviews remain `REVISIONS_REQUIRED`. Existing source-anchor judgments are
explicitly attributed to their prior assessment digest, and the new individual
rule/term judgments retain their own evidence bindings. They are not independent
reviews. Overlapping term/anchor findings are not unique defect counts or scores.

The Mini review preserves the unsupported earnings/regulatory-decision/industry-
shock references, unresolved contract-win mapping, publication mismatch, loan
timing/condition error, payment citation gap and missing risk qualifications.
The stronger answer's acquisition/strategic mapping remains a plausible author-
reviewed research proposal; its missing risk qualifications remain unresolved work.
No original answer, admission, source or earlier review was overwritten.

Private meaning-review verification manifest:
`530e0a13e5bbee589186a9f87edc496178c1939c57a79ee71f3a8c4dc3e4838a`.
Final v20 replay/preparation manifest:
`cc5d29f05b38f8ac9769ba35b0ad0ba85182d75e5c5bc9bcbf30b14175eb3b50`.
Artifacts are retained under `meaning-review-20260922` and
`semantic-offline-20260922`; source/master contents and
private review packets are not published in the PR. HTML structure, escaping,
internal links and exact regeneration passed automated checks. Browser visual
inspection was blocked by the local-file URL policy and is not claimed.

## Boundaries and next work

This step used **zero API calls and no credentials**. It does not establish a new
credit balance. KDP remains blocked by the unchanged complete-input limit; neither
truncation nor a limit increase is introduced. Broader input handling needs a
separate explicit design decision.

The new v20 instructions have not been sent to a provider. Another budgeted
comparison, including a source not used to develop these changes, is needed to
measure improvement. No reduction in model error or unattended qualification is
claimed here. The new review records are author judgments, not a held-out test.

Reviews use the exact governing masters frozen with each original request. Current
masters were not reread for new strategy decisions because none were made. No
Strategy v0.3/Experiment v0.5 methodology, risk, observation eligibility, synced
sources, Journal, production configuration or deployment changed. Phase 1 SHADOW
and disabled broker execution remain repository boundaries. Live runtime and
Journal state were not checked in this offline task.
