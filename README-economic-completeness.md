# Qualitative economic source coverage (opt-in v26)

## Problem and resulting behavior

The [v25 source review](README-binding-provider.md) found that a research answer
replaced substantive margin-expansion opportunity and substantial peak-capacity
increase with broad labels and a list of forward-looking topics. Unknown numeric
amounts were correctly unresolved, but that did not justify losing qualitative
effects. The original v25 admission and separate revision judgment remain intact.

Opt-in `1.25.0-automated-research` / `governed-research-v26` now requires an explicit
account of every substantive source passage. The host retains passages declared
as economic cores verbatim beside complete economic terms and in their materiality
links. Direction, magnitude and scope can therefore remain visible even when a
model's paraphrase is weak. Instructions require preserving those assertions in
the paraphrase too, with forecast nature and local qualifications.

This is a structural omission check and preservation mechanism. It does **not**
prove that the model selected the right passages or interpreted them completely.

## Finding / fix / evidence checklist

| Finding | Change | Regression evidence | Files | Remaining limitation |
| --- | --- | --- | --- | --- |
| Qualitative effects lost behind broad labels | Full-source instructions distinguish an economic assertion from a label or caution-topic list; exact original CORE passages accompany complete terms and summary links | Repeated synthetic headline retains margin opportunity, substantial peak-capacity increase and caution text; source offsets identify both occurrences | `research_completeness.py`, `tests/test_research_completeness.py` | A wrong paraphrase may remain; source review is required |
| Source material silently omitted | Each DOCUMENT_TEXT / NEWS_TEXT passage must be accounted for exactly once as CORE, QUALIFICATION, CONTEXT, OUT_OF_SCOPE or UNRESOLVED | Missing, duplicate, metadata and unknown passage numbers reject | Same | False exclusions can still pass; explicitly tested and exposed in review |
| Labels or caveats substitute for all core support | Each recorded term assertion requires a CORE association; term references must be valid and unique | Context-only and qualification-only maps cannot cover recorded cores; bad indices and invented core for an unresolved assertion reject | Same | Any substantive passage can be falsely declared core; no keyword-based semantic certification |
| Uncertainty hidden by a sufficient-coverage claim | UNRESOLVED passage classification cannot coexist with SUFFICIENT_FOR_RESEARCH | Conflict rejects; uncertainty and scoped exclusions remain reviewable | Same | These are declared classifications, not a new strategy threshold |
| Historical evidence or version attribution changed | Add a new explicit version and a separate `1.4.0-source-coverage-review` exporter; retain old implementations and original envelopes/text | Full request reconstruction, immutable originals, old response replay, attributed assessment and retry checks | `research_field_review.py`, `research_reviewer.py`, `review_attempts.py`, `evidence_review.py`, tests | Current model quality is untested |

## Contract and review

`economic_source_coverage` groups numbered passages, assigns a role, records
affected term indices where applicable, and explains the assignment. Groups may
span mechanical sentence/chunk boundaries. A mixed core-and-caution passage must
remain CORE, with all local qualifications preserved in its complete term.
Non-economic groups cannot claim term references. Every group, including every
exclusion, becomes a source-review item bound to its exact original value.

The host does not rewrite the original assertion or manufacture a numerical
amount. It derives occurrence-specific `economic_core_source_links` from captured
source text and includes them in `materiality_economic_links`, preserving the
complete term, original assertion, timing, conditions and qualifications. Links
are explicitly attributed as source claims, not verified outcomes.

Historical v25 schema and reports stay unchanged. CLI default remains v20; v26
requires explicit use of its request preparer. No automatic dispatch, credential
loading, new database migration or provider retry is introduced.

## Validation

**1,155 tests passed in 1,481.52 seconds**, including 34 new regressions. The
run records unchanged hashes for all 108 tested Python files. Tests use local
synthetic fixtures with network access blocked; none are Strategy observations.

The initial focused run had two test-fixture errors: an object-only schema check
was incorrectly applied to enum definitions, and a single-term unresolved fixture
retained an empty CORE group. Both fixtures were corrected without weakening
production validation before the passing full-suite run.

Test-result manifest:
`8cfbcf0cab5818bcdbe0807ddc015de23e5381a5f2a1d2940e861ae948232b97`.

All **124 historical outcomes replay exactly: 61 research admissions / 63
rejections**, across 28 unchanged ledgers. The complete v25 original report and
its separate `REVISIONS_REQUIRED` assessment reproduce exactly. Prior source,
answer, judgment, helper and ledger hashes remain unchanged.

Offline replay manifest:
`2f3bc27d1cc3d102e092132b9b50b996b48254102927bbbdc46f65956180934a`.

The full preserved source and all three governing-master texts remain in the
request. Fresh living-master revisions match the bound texts. The prepared
request is **156,778 bytes** and has not been sent. Input/output limits remain
250,000 bytes and 12,000 tokens, with failure rather than truncation.

A private implementation-author annotation marks the known omitted headline as
core and demonstrates exact host retention. Its unchanged original paraphrase
still requires revision. This is a synthetic infrastructure demonstration, not a
new provider answer, repaired historical result or measured model improvement.

## Boundaries and next evidence

**Zero paid API calls and no credential access in this step.** Provider acceptance
of the new schema and source quality of an actual v26 answer remain unverified.
A later bounded full-input test must review its original answer against the full
source, including every excluded passage and qualitative economic effect.

All outputs remain infrastructure evaluation, `eligible_for_handoff=false`,
`semantic_acceptance=NOT_ESTABLISHED`. No Strategy v0.3 or Experiment v0.5
methodology, qualification, risk, setup, trigger, stop, target or eligibility
change. No Journal/synced-source edit, production configuration change, merge,
deployment or execution enablement. Phase 1 SHADOW and disabled broker execution
remain repository boundaries. Live runtime configuration and live Journal state
were not verified. These checks do not establish hands-off readiness or profit.
