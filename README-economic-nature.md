# Economic result/forecast separation (v24)

## Problem and behavior

The [preserved v23 ADMA answer](README-role-provider.md) included a demonstrated
yield result and anticipated output/product benefits in one `REPORTED_RESULT`
term. Its local qualification reason omitted the forecast caution, although the
answer retained the caution elsewhere. The original remains unchanged.

Opt-in v24 keeps the full v23 wrapper and adds `term_classifications`. Each term
declares the nature and exact citations of its core assertion and every amounts
entry. Declarations that conflict with the containing term fail closed. Distinct
economic natures must occupy distinct terms, preserving both their substance and
applicable local qualifications. Existing obligation, commitment and other-nature
categories remain available; unavailable assertions retain empty source lists.

This validates consistency only. A model can still supply mutually consistent
but incorrect classifications. It does not establish source truth or complete
qualifications. [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
also does not guarantee correct content.

## Finding / fix / evidence / limitation checklist

| Finding | Change and files | Regression evidence | Remaining limitation |
| --- | --- | --- | --- |
| Reported result contains future benefits | `research_nature.py` binds core and amount-level natures to one term nature; conflicting declarations require separate terms. | Mixed result/forecast rejection; separately represented text retained; all old nested schema definitions preserved. | A consistent false declaration can pass; source review is required. |
| Local qualification scope incomplete | Prompt requires applicable qualifications on each affected term; `research_field_review.py` adds complete terms and nature declarations to attributed review. | Original facet/reason plus complete term included; exact decision coverage; revision cannot become semantic acceptance. | Scope prose is not machine-verified truth. No artificial mandatory caveat or numerical rule. |
| Historical outputs could change | Separate `1.23.0-automated-research` / `governed-research-v24` version, registered in `research_reviewer.py`, `review_attempts.py`, `evidence_review.py`. | Old request reconstruction, original envelopes/text retained, retry protection, pre-dispatch tamper rejection, historical replay. | Existing versions remain available and keep their historical behavior. |
| Economic detail could be lost in summaries | Existing lossless economic summary remains required for v24. | Full inventory rows and no-handoff flags verified. | Completeness still requires full-source review. |

`tests/test_research_nature.py` contains synthetic infrastructure cases. They are
not Strategy #1 observations or measured model improvement. A separately stored
author annotation of the original ADMA answer reproduces the new rejection;
neither the original response nor its admission or judgments are changed.

## Contract and review

`term_classifications` covers every term once. Each row contains `term_index`,
`core_nature`, `core_passages`, an exact `amount_natures` entry set, and a nonblank
`qualification_scope`. Amount entries retain their original citation set and have
a nature and reason. Indices are strict integers. Duplicate, missing, out-of-range
and conflicting declarations fail validation. Full inherited source, schema and
authority binding is checked before reserving or making a provider call.

The original full provider envelope, exact response text, wrapper, usage and
implementation versions remain in the review. Validation projections do not
replace originals. The complete economic term and its declaration join the
existing field checklist. New reports use `1.2.0-economic-nature-review`; historical
reports retain their previous versions and exact outputs.

All decisions require an attributable assessor, timestamp, original-value digest
and substantive source binding. Neither an all-supported assessment nor structural
acceptance grants semantic acceptance or handoff. The CLI still defaults to v20;
v24 requires explicit opt-in and has no automatic deployment or dispatch.

## Verification and provider evidence

- **1,078 tests passed in 999.67 seconds**, including 24 new regressions. All
  104 tested Python source hashes were unchanged during the run.
- All **122 historical outcomes replay exactly: 60 research admissions / 62
  rejections**, across 26 unchanged ledgers. Prior source/response/review hashes
  match, and the complete v23 report and attributed assessment regenerate exactly.
- The separately annotated full ADMA counterexample fails the new mixed-nature
  check. Original provider output is unchanged; no improvement rate is inferred.
- One full v24 request is prepared at 151,136 bytes, under the unchanged
  250,000-byte input and 12,000-output-token limits. All current living-master
  revisions match their bound texts. No API call occurred in this offline step.

Offline replay manifest:
`8a8819716c3bc1fc0929b6b3ba93e175a148aca83bd6bf2a3aa1da92be39ca64`.
Test result manifest:
`14c7c16f7233f867de9e0c492d80ae648fcf7dcb4815cce9c61eafd14969b669`.

The subsequent [bounded provider test and raw-answer review](README-nature-provider.md)
preserve the completed API answer and its host rejection for a citation-binding
mismatch. No retry or repaired admission was made. Structural API acceptance,
host validation and source-meaning review remain distinct evidence.

With the repository's dependencies installed, reproduce the checks with:

```text
python -m pytest -q tests/test_research_nature.py
python -m pytest -q
```

The existing read-only review CLI accepts v24 requests:

```text
python research_field_review.py --ledger attempts.sqlite --request-id ID --packet packet.json --reference reference.json --output reports
python research_field_review.py --ledger attempts.sqlite --request-id ID --packet packet.json --reference reference.json --assessment assessment.json --output reports
```

## Boundaries

No migration is needed. No strategy/experiment methodology, risk limit, setup,
trigger, stop, target or eligibility change. Phase 1 remains SHADOW with broker
execution disabled in repository boundaries. No production configuration change,
merge, deployment, Journal write or synced-source edit is part of this work.
Live runtime configuration and live Journal state were not verified.
