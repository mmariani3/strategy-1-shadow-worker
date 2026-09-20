# Attributed offline completeness review

`research_completeness_review.py` records explicit source/prose judgments after the
[reference-location audit](README-reference-coverage.md). Valid citations alone
cannot establish that a summary preserves economically important information.
This separate review stage makes no API calls and does not change the v14 model
prompt, admission parser, original responses or historical outcomes.

## Review procedure

1. Preserve the original provider response, request, source packet and attributed
   reference. Establish response provenance from the saved provider ledger.
2. Generate an unresolved checklist with the command below. Read the source and
   corresponding original prose, including passages outside the selected citations.
3. Review **fees/economic terms, conditions, timing and counterevidence** for the
   declared summary scope. For every supplied reference anchor, record relevance,
   finding, rationale and exact original draft paths/value digests. Record assessor
   identity, kind, timestamp and limitations. An unresolved judgment stays unresolved.
4. Save the completed assessment as a new file and record it with `--assessment`.
   Preserve prior assessments. Resolve requested revisions in a separately attributed
   future answer; never edit an original answer to make an old test pass.

These four aspects are an engineering review checklist, not new strategy eligibility
criteria or a required document type. Materiality depends on the declared scope and
governing masters. Software does not decide economic relevance or certify an assessor.

```text
python research_completeness_review.py --packet PRIVATE_PACKET.json --request PRIVATE_V14_REQUEST.json --draft ORIGINAL_DRAFT.json --reference PRIVATE_REFERENCE.json --output PRIVATE_REVIEW_FOLDER
```

The default writes a template with every judgment unresolved and assessor unassigned.
After explicit review, append `--assessment ATTRIBUTED_ASSESSMENT.json` to record it.
Missing/duplicate anchors or aspects, mismatched scope, altered source/draft bindings,
invalid evidence paths/digests and invalid review timestamps fail closed. Evidence
paths are JSON key/index arrays; `value_digest` is SHA-256 of the existing canonical
JSON encoding of the selected original value. The generated template supplies an
initial binding to the original materiality statement; choose more specific paths
where needed to support the judgment. Source quotes remain in the validated reference.

## Meaning of the record

Findings distinguish `PRESERVED`, `MATERIAL_OMISSION`, `MEANING_ERROR`, `CITATION_GAP`
and `UNRESOLVED`. A material omission requires explicit `REQUIRED_FOR_SCOPE` relevance.
A citation gap is not automatically a missing fact. A selected passage is not proof
that the model interpreted it correctly.

- `REVISIONS_REQUIRED`: at least one recorded omission, meaning error or citation gap.
  Any unresolved issues remain separately visible.
- `REVIEW_REQUIRED`: no recorded revision yet, but judgments/aspects or selections
  remain unresolved/invalid.
- `SCOPED_REVIEW_RECORDED`: the supplied checklist is reviewed with no revision flags.
  It does **not** establish complete source understanding or semantic acceptance.

Aspect `REVIEWED` means inspected, not passed. `NOT_APPLICABLE` still requires a
rationale and reference anchor. Every result retains `summary_completeness` and
`semantic_acceptance` as `NOT_ESTABLISHED`, `eligible_for_handoff=false`, and
`classification=INFRASTRUCTURE_EVALUATION`. Original admission is never reevaluated.
Software verifies bindings and checklist coverage; assessor truthfulness, judgment,
independence and reference inventory completeness remain outside its verification.

## September 19 development review

The implementation author reviewed 30 supplied anchor/answer combinations and all
16 aspect checks across the four saved v14 answers. These are post-response AI
judgments on reused ABTS/CVI cases, not independent acceptance or held-out evidence.

| Saved answer | Separate review status | Key source/prose finding |
| --- | --- | --- |
| ABTS / Mini | REVISIONS_REQUIRED | Missing noncontingent $7.5M fee, default-and-day-180 conversion conditions and explicit substantial-dilution warning; conditional-funding citation gap; document/strategy-label confusion. Note-term adequacy remains unresolved. |
| ABTS / GPT-5.5 | REVISIONS_REQUIRED | Financing summary omits the noncontingent $7.5M commitment fee despite structural admission. |
| CVI / Mini | REVISIONS_REQUIRED | Identity and technical-warning citation gaps; primary-document/setup requirements confused with materiality. |
| CVI / GPT-5.5 | REVIEW_REQUIRED | Supplied source facts preserved; earnings-category and benchmark interpretation remain unresolved. |

Mini did preserve concepts such as conditional funding and an overbought warning.
Their missing reference selections therefore warranted citation review, not an
automatic material-omission label. No new tier approval, freshness duration,
materiality cutoff or universal primary-document requirement was introduced.

The records preserve original source quotes, original model text, request/draft/
reference digests, trace identifiers, assessor attribution and implementation version.
The private run manifest verifies the original 16 ledger hashes and identifies the
four provider responses. This generic CLI cannot authenticate arbitrary JSON as a
provider response; its caller must preserve and verify that provenance.

## Verification and next boundary

Twenty new regressions cover default unresolved templates, valid citations with
false prose, omission/citation distinctions, pending issues retained after revision
flags, optional context, binding/timestamp failures, immutable input files and no
admission promotion. Run `python -m pytest -q` with the existing project dependencies.

Validation on this change: **730 tests passed**. All **97 historical outcomes**
replayed unchanged (43 research admissions, 54 rejections); sixteen original ledger
hashes remained unchanged. No API calls were made for this offline review.

This implements the offline review procedure. It does not demonstrate improved
future model answers or automatically discover missing fee clauses. A future prompt
or extraction change needs its own version, regression review and a separately
budgeted comparison on new source documents. Resolve funding before paid testing;
do not shrink a test to conceal an insufficient balance. Neither model is accepted
for unattended qualification. Phase 1 remains SHADOW; no production deployment,
broker enablement, journal write, schema migration or methodology change is included.
